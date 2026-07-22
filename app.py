from flask import Flask, request, abort
import os
import json
import traceback
from urllib.parse import parse_qs

import requests
from openai import OpenAI

from richmenu_manager import get_home_rich_menu_id

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    QuickReply,
    QuickReplyItem,
    PostbackAction,
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    PostbackEvent,
    FollowEvent,
    JoinEvent,
)


# =========================================================
# Flask 與環境變數
# =========================================================

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")


required_env = {
    "CHANNEL_ACCESS_TOKEN": CHANNEL_ACCESS_TOKEN,
    "CHANNEL_SECRET": CHANNEL_SECRET,
    "OPENAI_API_KEY": OPENAI_API_KEY,
}

missing_env = [name for name, value in required_env.items() if not value]

if missing_env:
    raise ValueError(
        "缺少必要環境變數：" + ", ".join(missing_env)
    )


# =========================================================
# 路徑與身份設定
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = os.path.join(BASE_DIR, "static", "tmp")

ROLE_CONFIG = {
    "family": {
        "name": "家屬",
        "env_name": "FAMILY_RICH_MENU_ID",
    },
    "caregiver": {
        "name": "看護",
        "env_name": "CAREGIVER_RICH_MENU_ID",
    },
    "elderly": {
        "name": "長者",
        "env_name": "ELDERLY_RICH_MENU_ID",
    },
}


# =========================================================
# LINE 與 OpenAI 初始化
# =========================================================

configuration = Configuration(
    access_token=CHANNEL_ACCESS_TOKEN
)

handler = WebhookHandler(CHANNEL_SECRET)
openai_client = OpenAI(api_key=OPENAI_API_KEY)


def get_messaging_api():
    api_client = ApiClient(configuration)
    return api_client, MessagingApi(api_client)


def get_blob_api():
    api_client = ApiClient(configuration)
    return api_client, MessagingApiBlob(api_client)


# =========================================================
# 共用函式
# =========================================================

def safe_text(text, limit=5000):
    text = str(text or "")

    if len(text) <= limit:
        return text

    return text[: limit - 3] + "..."


def get_user_id(event):
    source = getattr(event, "source", None)
    return getattr(source, "user_id", None) if source else None


def reply_text(reply_token, text):
    api_client, messaging_api = get_messaging_api()

    try:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(text=safe_text(text))
                ],
            )
        )
    finally:
        api_client.close()


# =========================================================
# PostgreSQL 資料庫
# =========================================================

def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "缺少 DATABASE_URL，無法連線 PostgreSQL"
        )

    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError(
            "使用 PostgreSQL 時需安裝 psycopg2-binary"
        ) from error

    return psycopg2.connect(DATABASE_URL)


def init_database():
    """
    驗證新版 PostgreSQL 架構是否已建立。
    不再建立舊的 line_users 資料表。
    """
    required_tables = {
        "roles",
        "languages",
        "app_users",
        "rich_menus",
        "user_rich_menu_bindings",
        "operation_logs",
    }

    connection = get_db_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )

        existing_tables = {
            row[0]
            for row in cursor.fetchall()
        }

        missing_tables = sorted(
            required_tables - existing_tables
        )

        if missing_tables:
            raise RuntimeError(
                "新版 PostgreSQL 架構尚未完成，缺少資料表："
                + ", ".join(missing_tables)
            )

    finally:
        connection.close()


def get_default_language_code(role, profile_language=None):
    """
    優先使用 LINE Profile 回傳語言。
    若資料庫未支援該語言，save_user() 會回退到身份預設語言。
    """
    if profile_language:
        return profile_language

    if role == "caregiver":
        return "en"

    return "zh-TW"


def get_user(user_id):
    if not user_id:
        return None

    connection = get_db_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                u.id,
                u.line_user_id AS user_id,
                u.display_name,
                r.code AS role,
                u.current_rich_menu_id AS rich_menu_id,
                u.picture_url,
                l.code AS language,
                u.created_at,
                u.updated_at,
                u.last_seen_at
            FROM app_users u
            JOIN roles r
                ON r.id = u.role_id
            LEFT JOIN languages l
                ON l.id = u.language_id
            WHERE u.line_user_id = %s
              AND u.is_active = TRUE
            """,
            (user_id,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        columns = [
            column[0]
            for column in cursor.description
        ]
        return dict(zip(columns, row))

    finally:
        connection.close()


def get_role_rich_menu_id_from_database(role):
    """
    從 rich_menus 取得該身份啟用中的首頁 Rich Menu。
    caregiver 預設使用英文；其他身份預設繁體中文。
    """
    language_code = (
        "en"
        if role == "caregiver"
        else "zh-TW"
    )

    connection = get_db_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT rm.line_rich_menu_id
            FROM rich_menus rm
            JOIN roles r
                ON r.id = rm.role_id
            JOIN languages l
                ON l.id = rm.language_id
            WHERE r.code = %s
              AND l.code = %s
              AND rm.is_home = TRUE
              AND rm.is_active = TRUE
              AND rm.line_rich_menu_id IS NOT NULL
            ORDER BY rm.updated_at DESC
            LIMIT 1
            """,
            (role, language_code),
        )

        row = cursor.fetchone()
        return row[0] if row else None

    finally:
        connection.close()


def get_role_rich_menu_id(role):
    """
    取得身份對應首頁 Rich Menu ID。

    優先順序：
    1. PostgreSQL rich_menus
    2. Render 環境變數
    3. richmenu_ids.json
    """
    database_value = get_role_rich_menu_id_from_database(
        role
    )

    if database_value:
        return database_value

    role_setting = ROLE_CONFIG.get(role)

    if not role_setting:
        return None

    env_name = role_setting.get("env_name")
    env_value = os.getenv(env_name) if env_name else None

    if env_value:
        return env_value.strip()

    return get_home_rich_menu_id(role)


def save_user(
    user_id,
    display_name,
    role,
    rich_menu_id=None,
    picture_url=None,
    language=None,
):
    """
    儲存或更新 LINE 使用者、身份、語言及目前 Rich Menu。
    """
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM roles
            WHERE code = %s
              AND is_active = TRUE
            """,
            (role,),
        )
        role_row = cursor.fetchone()

        if not role_row:
            raise RuntimeError(
                f"資料庫找不到身份代碼：{role}"
            )

        role_id = role_row[0]
        requested_language = get_default_language_code(
            role,
            language,
        )

        cursor.execute(
            """
            SELECT id
            FROM languages
            WHERE code = %s
              AND is_active = TRUE
            """,
            (requested_language,),
        )
        language_row = cursor.fetchone()

        if not language_row:
            fallback_language = (
                "en"
                if role == "caregiver"
                else "zh-TW"
            )

            cursor.execute(
                """
                SELECT id
                FROM languages
                WHERE code = %s
                  AND is_active = TRUE
                """,
                (fallback_language,),
            )
            language_row = cursor.fetchone()

        language_id = (
            language_row[0]
            if language_row
            else None
        )

        cursor.execute(
            """
            INSERT INTO app_users (
                line_user_id,
                display_name,
                picture_url,
                role_id,
                language_id,
                current_rich_menu_id,
                is_active,
                last_seen_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, TRUE,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT (line_user_id)
            DO UPDATE SET
                display_name = EXCLUDED.display_name,
                picture_url = EXCLUDED.picture_url,
                role_id = EXCLUDED.role_id,
                language_id = EXCLUDED.language_id,
                current_rich_menu_id =
                    EXCLUDED.current_rich_menu_id,
                is_active = TRUE,
                last_seen_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (
                user_id,
                display_name,
                picture_url,
                role_id,
                language_id,
                rich_menu_id,
            ),
        )

        app_user_id = cursor.fetchone()[0]
        connection.commit()
        return app_user_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def record_rich_menu_binding(
    line_user_id,
    role,
    line_rich_menu_id,
    success=True,
    error_message=None,
):
    """
    記錄使用者目前綁定的 Rich Menu。
    成功時會將前一筆 is_current 改為 FALSE。
    """
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM app_users
            WHERE line_user_id = %s
            """,
            (line_user_id,),
        )
        user_row = cursor.fetchone()

        if not user_row:
            raise RuntimeError(
                "記錄 Rich Menu 綁定時找不到使用者"
            )

        app_user_id = user_row[0]

        cursor.execute(
            """
            SELECT rm.id
            FROM rich_menus rm
            JOIN roles r
                ON r.id = rm.role_id
            WHERE r.code = %s
              AND rm.line_rich_menu_id = %s
              AND rm.is_active = TRUE
            LIMIT 1
            """,
            (role, line_rich_menu_id),
        )
        menu_row = cursor.fetchone()

        if success and menu_row:
            rich_menu_uuid = menu_row[0]

            cursor.execute(
                """
                UPDATE user_rich_menu_bindings
                SET
                    is_current = FALSE,
                    unbound_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                  AND is_current = TRUE
                """,
                (app_user_id,),
            )

            cursor.execute(
                """
                INSERT INTO user_rich_menu_bindings (
                    user_id,
                    rich_menu_id,
                    line_rich_menu_id,
                    is_current,
                    error_message
                )
                VALUES (%s, %s, %s, TRUE, NULL)
                """,
                (
                    app_user_id,
                    rich_menu_uuid,
                    line_rich_menu_id,
                ),
            )

            cursor.execute(
                """
                UPDATE app_users
                SET
                    current_rich_menu_id = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    line_rich_menu_id,
                    app_user_id,
                ),
            )

        cursor.execute(
            """
            INSERT INTO operation_logs (
                user_id,
                action_type,
                entity_type,
                entity_id,
                details,
                success,
                error_message
            )
            VALUES (
                %s,
                %s,
                'rich_menu',
                %s,
                %s::jsonb,
                %s,
                %s
            )
            """,
            (
                app_user_id,
                (
                    "rich_menu_bound"
                    if success
                    else "rich_menu_bind_failed"
                ),
                (
                    menu_row[0]
                    if menu_row
                    else None
                ),
                json.dumps(
                    {
                        "role": role,
                        "line_rich_menu_id": (
                            line_rich_menu_id
                        ),
                    },
                    ensure_ascii=False,
                ),
                success,
                error_message,
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def record_role_selection(
    line_user_id,
    role,
):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id
            FROM app_users
            WHERE line_user_id = %s
            """,
            (line_user_id,),
        )
        row = cursor.fetchone()

        if not row:
            return

        cursor.execute(
            """
            INSERT INTO operation_logs (
                user_id,
                action_type,
                entity_type,
                details,
                success
            )
            VALUES (
                %s,
                'role_selected',
                'role',
                %s::jsonb,
                TRUE
            )
            """,
            (
                row[0],
                json.dumps(
                    {"role": role},
                    ensure_ascii=False,
                ),
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# 身份選擇
# =========================================================

def create_role_selection_message():
    return TextMessage(
        text=(
            "歡迎使用長照用藥 Bot！\n\n"
            "請先選擇您的身份類別。"
        ),
        quick_reply=QuickReply(
            items=[
                QuickReplyItem(
                    action=PostbackAction(
                        label="家屬",
                        data="action=select_role&role=family",
                        display_text="我是家屬",
                    )
                ),
                QuickReplyItem(
                    action=PostbackAction(
                        label="看護",
                        data="action=select_role&role=caregiver",
                        display_text="我是看護",
                    )
                ),
                QuickReplyItem(
                    action=PostbackAction(
                        label="長者",
                        data="action=select_role&role=elderly",
                        display_text="我是長者",
                    )
                ),
            ]
        ),
    )


def reply_role_selection(reply_token):
    api_client, messaging_api = get_messaging_api()

    try:
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    create_role_selection_message()
                ],
            )
        )
    finally:
        api_client.close()


# =========================================================
# LINE 使用者資料與 Rich Menu
# =========================================================

def get_line_profile(user_id):
    api_client, messaging_api = get_messaging_api()

    try:
        profile = messaging_api.get_profile(
            user_id=user_id
        )

        return {
            "display_name": getattr(
                profile,
                "display_name",
                "使用者",
            ),
            "picture_url": getattr(
                profile,
                "picture_url",
                None,
            ),
            "language": getattr(
                profile,
                "language",
                None,
            ),
        }

    finally:
        api_client.close()


def link_rich_menu(user_id, rich_menu_id):
    if not user_id:
        raise RuntimeError("無法取得 LINE User ID")

    if not rich_menu_id:
        raise RuntimeError(
            "找不到對應的 Rich Menu ID。"
            "請確認 richmenu_ids.json 已建立，"
            "或 Render 環境變數已設定。"
        )

    url = (
        "https://api.line.me/v2/bot/user/"
        f"{user_id}/richmenu/{rich_menu_id}"
    )

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
        },
        timeout=20,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Rich Menu 綁定失敗："
            f"HTTP {response.status_code} "
            f"{response.text}"
        )

    app.logger.info(
        "Rich Menu 綁定成功：user_id=%s, rich_menu_id=%s",
        user_id,
        rich_menu_id,
    )

    return True


def bind_role_rich_menu(user_id, role):
    rich_menu_id = get_role_rich_menu_id(role)

    if not rich_menu_id:
        raise RuntimeError(
            f"身份 {role} 尚未取得首頁 Rich Menu ID"
        )

    try:
        link_rich_menu(user_id, rich_menu_id)

        record_rich_menu_binding(
            line_user_id=user_id,
            role=role,
            line_rich_menu_id=rich_menu_id,
            success=True,
        )

        return rich_menu_id

    except Exception as error:
        try:
            record_rich_menu_binding(
                line_user_id=user_id,
                role=role,
                line_rich_menu_id=rich_menu_id,
                success=False,
                error_message=str(error),
            )
        except Exception:
            app.logger.error(
                "記錄 Rich Menu 綁定失敗時發生錯誤"
            )
            app.logger.error(traceback.format_exc())

        raise



# =========================================================
# 家庭管理功能
# =========================================================

FAMILY_ACTIONS = {
    "family_add_elder",
    "family_manage_elder",
    "family_add_caregiver",
    "family_assign_caregiver",
    "family_bind_group",
    "family_confirm_add_elder",
    "family_confirm_add_caregiver",
    "family_remove_elder",
    "family_confirm_remove_elder",
    "family_select_caregiver",
    "family_select_elder_for_caregiver",
    "family_confirm_assignment",
    "family_cancel",
}


def reply_message(reply_token, message):
    api_client, messaging_api = get_messaging_api()
    try:
        messaging_api.reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[message])
        )
    finally:
        api_client.close()


def make_quick_reply_message(text, items):
    return TextMessage(
        text=safe_text(text),
        quick_reply=QuickReply(items=items),
    )


def postback_item(label, data, display_text=None):
    return QuickReplyItem(
        action=PostbackAction(
            label=label[:20],
            data=data,
            display_text=(display_text or label)[:300],
        )
    )


def get_app_user_by_line_id(line_user_id):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT u.id, u.line_user_id, u.display_name, r.code AS role
            FROM app_users u
            JOIN roles r ON r.id = u.role_id
            WHERE u.line_user_id = %s AND u.is_active = TRUE
            """,
            (line_user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {"id": row[0], "line_user_id": row[1], "display_name": row[2], "role": row[3]}
    finally:
        connection.close()


def get_or_create_family_for_admin(line_user_id):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, display_name FROM app_users WHERE line_user_id=%s AND is_active=TRUE", (line_user_id,))
        user = cursor.fetchone()
        if not user:
            raise RuntimeError("找不到目前家屬的使用者資料")
        user_id, display_name = user
        cursor.execute(
            """
            SELECT f.id, f.family_name
            FROM families f
            JOIN family_members fm ON fm.family_id=f.id
            WHERE fm.user_id=%s AND fm.member_role='family' AND fm.is_active=TRUE AND f.is_active=TRUE
            ORDER BY fm.created_at LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return {"id": row[0], "family_name": row[1], "admin_user_id": user_id}
        family_name = f"{display_name or '家屬'}的家庭"
        cursor.execute("INSERT INTO families (family_name, created_by) VALUES (%s,%s) RETURNING id", (family_name, user_id))
        family_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO family_members (family_id,user_id,member_role,is_admin,is_active,added_by)
            VALUES (%s,%s,'family',TRUE,TRUE,%s)
            """,
            (family_id, user_id, user_id),
        )
        connection.commit()
        return {"id": family_id, "family_name": family_name, "admin_user_id": user_id}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def set_operation_state(line_user_id, action, step, payload=None):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM app_users WHERE line_user_id=%s", (line_user_id,))
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("找不到使用者資料")
        cursor.execute(
            """
            INSERT INTO user_operation_states (user_id,action,step,payload,updated_at)
            VALUES (%s,%s,%s,%s::jsonb,CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
              action=EXCLUDED.action, step=EXCLUDED.step, payload=EXCLUDED.payload,
              updated_at=CURRENT_TIMESTAMP
            """,
            (row[0], action, step, json.dumps(payload or {}, ensure_ascii=False)),
        )
        connection.commit()
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()


def get_operation_state(line_user_id):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT s.action,s.step,s.payload
            FROM user_operation_states s JOIN app_users u ON u.id=s.user_id
            WHERE u.line_user_id=%s
            """, (line_user_id,)
        )
        row=cursor.fetchone()
        return {"action":row[0],"step":row[1],"payload":row[2] or {}} if row else None
    finally:
        connection.close()


def clear_operation_state(line_user_id):
    connection=get_db_connection()
    try:
        cursor=connection.cursor()
        cursor.execute("DELETE FROM user_operation_states USING app_users u WHERE user_operation_states.user_id=u.id AND u.line_user_id=%s", (line_user_id,))
        connection.commit()
    finally:
        connection.close()


def ensure_family_admin(line_user_id):
    user=get_app_user_by_line_id(line_user_id)
    if not user or user["role"] != "family":
        raise RuntimeError("只有家屬身份可以使用家庭管理功能")
    return get_or_create_family_for_admin(line_user_id)


def list_family_members(family_id, member_role):
    connection=get_db_connection()
    try:
        cursor=connection.cursor()
        cursor.execute(
            """
            SELECT u.id,u.line_user_id,u.display_name
            FROM family_members fm JOIN app_users u ON u.id=fm.user_id
            WHERE fm.family_id=%s AND fm.member_role=%s AND fm.is_active=TRUE AND u.is_active=TRUE
            ORDER BY u.display_name,u.created_at
            """, (family_id,member_role)
        )
        return [{"id":r[0],"line_user_id":r[1],"display_name":r[2] or "未命名使用者"} for r in cursor.fetchall()]
    finally:
        connection.close()


def bind_member_to_family(family_id, target_user_id, member_role, added_by):
    connection=get_db_connection()
    try:
        cursor=connection.cursor()
        cursor.execute(
            """
            INSERT INTO family_members (family_id,user_id,member_role,is_admin,is_active,added_by,removed_at)
            VALUES (%s,%s,%s,FALSE,TRUE,%s,NULL)
            ON CONFLICT (family_id,user_id) DO UPDATE SET member_role=EXCLUDED.member_role,is_active=TRUE,added_by=EXCLUDED.added_by,removed_at=NULL,updated_at=CURRENT_TIMESTAMP
            """, (family_id,target_user_id,member_role,added_by)
        )
        connection.commit()
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()


def remove_elder_from_family(family_id, elder_user_id, removed_by):
    connection=get_db_connection()
    try:
        cursor=connection.cursor()
        cursor.execute("UPDATE family_members SET is_active=FALSE,removed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE family_id=%s AND user_id=%s AND member_role='elderly' AND is_active=TRUE", (family_id,elder_user_id))
        if cursor.rowcount == 0:
            raise RuntimeError("找不到這位長者的有效家庭綁定")
        cursor.execute("UPDATE caregiver_patient_assignments SET is_active=FALSE,ended_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE family_id=%s AND elder_user_id=%s AND is_active=TRUE", (family_id,elder_user_id))
        connection.commit()
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()


def assign_caregiver(family_id, caregiver_user_id, elder_user_id, assigned_by):
    connection=get_db_connection()
    try:
        cursor=connection.cursor()
        cursor.execute(
            """
            INSERT INTO caregiver_patient_assignments (family_id,caregiver_user_id,elder_user_id,assigned_by,is_active,ended_at)
            VALUES (%s,%s,%s,%s,TRUE,NULL)
            ON CONFLICT (family_id,caregiver_user_id,elder_user_id) DO UPDATE SET is_active=TRUE,assigned_by=EXCLUDED.assigned_by,ended_at=NULL,updated_at=CURRENT_TIMESTAMP
            """, (family_id,caregiver_user_id,elder_user_id,assigned_by)
        )
        connection.commit()
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()


def bind_group_to_family(family_id, group_id, bound_by):
    if not group_id or not group_id.startswith("C") or len(group_id) < 20:
        raise RuntimeError("群組 ID 格式不正確，LINE 群組 ID 通常以 C 開頭")
    connection=get_db_connection()
    try:
        cursor=connection.cursor()
        cursor.execute(
            """
            INSERT INTO family_line_groups (family_id,line_group_id,bound_by,is_active)
            VALUES (%s,%s,%s,TRUE)
            ON CONFLICT (line_group_id) DO UPDATE SET family_id=EXCLUDED.family_id,bound_by=EXCLUDED.bound_by,is_active=TRUE,updated_at=CURRENT_TIMESTAMP
            """, (family_id,group_id,bound_by)
        )
        connection.commit()
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()


def handle_family_text_input(event, user_text, user_id):
    state=get_operation_state(user_id)
    if not state:
        return False
    family=ensure_family_admin(user_id)
    admin_id=family["admin_user_id"]
    if state["step"] == "waiting_elder_id":
        target=get_app_user_by_line_id(user_text)
        if not target:
            reply_text(event.reply_token,"找不到這個 LINE User ID。請確認對方已加入 Bot 並完成身份設定。\n輸入「取消」可結束操作。")
            return True
        if target["role"] != "elderly":
            reply_text(event.reply_token,f"此使用者身份是「{ROLE_CONFIG.get(target['role'],{}).get('name',target['role'])}」，不是長者。")
            return True
        set_operation_state(user_id,"family_add_elder","confirm",{"target_id":str(target["id"]),"line_user_id":target["line_user_id"],"display_name":target["display_name"]})
        reply_message(event.reply_token, make_quick_reply_message(f"找到長者：{target['display_name'] or '未命名'}\nLINE User ID：{target['line_user_id']}\n\n確定加入您的家庭？", [postback_item("確認新增","action=family_confirm_add_elder"),postback_item("取消","action=family_cancel")]))
        return True
    if state["step"] == "waiting_caregiver_id":
        target=get_app_user_by_line_id(user_text)
        if not target:
            reply_text(event.reply_token,"找不到這個 LINE User ID。請確認對方已加入 Bot 並完成身份設定。")
            return True
        if target["role"] != "caregiver":
            reply_text(event.reply_token,"這個帳號不是看護身份，無法加入。")
            return True
        set_operation_state(user_id,"family_add_caregiver","confirm",{"target_id":str(target["id"]),"line_user_id":target["line_user_id"],"display_name":target["display_name"]})
        reply_message(event.reply_token, make_quick_reply_message(f"找到看護：{target['display_name'] or '未命名'}\nLINE User ID：{target['line_user_id']}\n\n確定加入您的家庭？", [postback_item("確認新增","action=family_confirm_add_caregiver"),postback_item("取消","action=family_cancel")]))
        return True
    if state["step"] == "waiting_group_id":
        bind_group_to_family(family["id"],user_text,admin_id)
        clear_operation_state(user_id)
        reply_text(event.reply_token,f"家庭群組綁定完成！\nGroup ID：{user_text}")
        return True
    return False


def handle_family_postback(event, action, params):
    user_id=get_user_id(event)
    if not user_id:
        reply_text(event.reply_token,"無法取得您的 LINE User ID。")
        return True
    if action == "family_cancel":
        clear_operation_state(user_id); reply_text(event.reply_token,"已取消本次家庭管理操作。")
        return True
    family=ensure_family_admin(user_id); family_id=family["id"]; admin_id=family["admin_user_id"]
    if action == "family_add_elder":
        set_operation_state(user_id,action,"waiting_elder_id")
        reply_text(event.reply_token,"請輸入長者的 LINE User ID。\n\n對方必須先加入 Bot，並將身份設定為「長者」。\n輸入「取消」可結束操作。")
    elif action == "family_confirm_add_elder":
        state=get_operation_state(user_id)
        if not state or not state.get("payload",{}).get("target_id"):
            raise RuntimeError("新增資料已逾時，請重新操作")
        import uuid
        bind_member_to_family(family_id,uuid.UUID(state["payload"]["target_id"]),"elderly",admin_id)
        clear_operation_state(user_id)
        reply_text(event.reply_token,f"已成功新增長者：{state['payload'].get('display_name') or '未命名'}")
    elif action == "family_manage_elder":
        elders=list_family_members(family_id,"elderly")
        if not elders:
            reply_text(event.reply_token,"目前家庭尚未綁定任何長者。")
        else:
            items=[postback_item(e["display_name"],f"action=family_remove_elder&elder_id={e['id']}",f"管理 {e['display_name']}") for e in elders[:12]]
            reply_message(event.reply_token,make_quick_reply_message("請選擇要從家庭中移除的長者：",items))
    elif action == "family_remove_elder":
        elder_id=params.get("elder_id",[None])[0]
        elders={str(e["id"]):e for e in list_family_members(family_id,"elderly")}
        if elder_id not in elders: raise RuntimeError("找不到這位長者")
        set_operation_state(user_id,action,"confirm_remove",{"elder_id":elder_id,"display_name":elders[elder_id]["display_name"]})
        reply_message(event.reply_token,make_quick_reply_message(f"確定要將「{elders[elder_id]['display_name']}」移出家庭嗎？\n相關看護指派也會解除。",[postback_item("確認移除","action=family_confirm_remove_elder"),postback_item("取消","action=family_cancel")]))
    elif action == "family_confirm_remove_elder":
        state=get_operation_state(user_id); import uuid
        if not state or not state.get("payload",{}).get("elder_id"): raise RuntimeError("移除資料已逾時")
        remove_elder_from_family(family_id,uuid.UUID(state["payload"]["elder_id"]),admin_id)
        name=state["payload"].get("display_name"); clear_operation_state(user_id)
        reply_text(event.reply_token,f"已將「{name}」移出家庭。")
    elif action == "family_add_caregiver":
        set_operation_state(user_id,action,"waiting_caregiver_id")
        reply_text(event.reply_token,"請輸入看護的 LINE User ID。\n\n對方必須先加入 Bot，並將身份設定為「看護」。\n輸入「取消」可結束操作。")
    elif action == "family_confirm_add_caregiver":
        state=get_operation_state(user_id); import uuid
        if not state or not state.get("payload",{}).get("target_id"): raise RuntimeError("新增資料已逾時")
        bind_member_to_family(family_id,uuid.UUID(state["payload"]["target_id"]),"caregiver",admin_id)
        clear_operation_state(user_id)
        reply_text(event.reply_token,f"已成功新增看護：{state['payload'].get('display_name') or '未命名'}")
    elif action == "family_assign_caregiver":
        caregivers=list_family_members(family_id,"caregiver")
        if not caregivers: reply_text(event.reply_token,"目前家庭尚未新增任何看護。")
        else:
            items=[postback_item(c["display_name"],f"action=family_select_caregiver&caregiver_id={c['id']}") for c in caregivers[:12]]
            reply_message(event.reply_token,make_quick_reply_message("請選擇要指派的看護：",items))
    elif action == "family_select_caregiver":
        caregiver_id=params.get("caregiver_id",[None])[0]
        caregivers={str(c["id"]):c for c in list_family_members(family_id,"caregiver")}
        if caregiver_id not in caregivers: raise RuntimeError("找不到這位看護")
        elders=list_family_members(family_id,"elderly")
        if not elders: reply_text(event.reply_token,"目前家庭尚未新增任何長者。")
        else:
            set_operation_state(user_id,"family_assign_caregiver","select_elder",{"caregiver_id":caregiver_id,"caregiver_name":caregivers[caregiver_id]["display_name"]})
            items=[postback_item(e["display_name"],f"action=family_select_elder_for_caregiver&elder_id={e['id']}") for e in elders[:12]]
            reply_message(event.reply_token,make_quick_reply_message(f"已選擇看護：{caregivers[caregiver_id]['display_name']}\n請選擇要照顧的長者：",items))
    elif action == "family_select_elder_for_caregiver":
        state=get_operation_state(user_id); elder_id=params.get("elder_id",[None])[0]
        elders={str(e["id"]):e for e in list_family_members(family_id,"elderly")}
        if not state or elder_id not in elders: raise RuntimeError("指派資料已逾時或長者不存在")
        payload=state["payload"]; payload.update({"elder_id":elder_id,"elder_name":elders[elder_id]["display_name"]})
        set_operation_state(user_id,"family_assign_caregiver","confirm_assignment",payload)
        reply_message(event.reply_token,make_quick_reply_message(f"看護：{payload['caregiver_name']}\n長者：{payload['elder_name']}\n\n確定建立照護指派？",[postback_item("確認指派","action=family_confirm_assignment"),postback_item("取消","action=family_cancel")]))
    elif action == "family_confirm_assignment":
        state=get_operation_state(user_id); import uuid
        payload=state.get("payload",{}) if state else {}
        if not payload.get("caregiver_id") or not payload.get("elder_id"): raise RuntimeError("指派資料已逾時")
        assign_caregiver(family_id,uuid.UUID(payload["caregiver_id"]),uuid.UUID(payload["elder_id"]),admin_id)
        clear_operation_state(user_id)
        reply_text(event.reply_token,f"指派完成！\n看護：{payload['caregiver_name']}\n長者：{payload['elder_name']}")
    elif action == "family_bind_group":
        set_operation_state(user_id,action,"waiting_group_id")
        reply_text(event.reply_token,"請貼上 LINE 家庭群組 ID。\n\n先將 Bot 加入家庭群組，Bot 會在群組內顯示 Group ID。")
    else:
        return False
    return True

# =========================================================
# OpenAI
# =========================================================

def gpt_response(user_text):
    response = openai_client.responses.create(
        prompt={
            "id": (
                "pmpt_69e86fa11c1c8193bf0389182d0c664c"
                "0cc0ed66294ebdce"
            ),
            "version": "3",
        },
        input=user_text,
    )

    answer = getattr(
        response,
        "output_text",
        "",
    ).strip()

    return answer or "目前沒有取得回應，請再試一次。"


# =========================================================
# Flask 路由
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return (
        "LINE Bot is running. "
        "Database: PostgreSQL"
    )


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get(
        "X-Line-Signature",
        "",
    )
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)

    except InvalidSignatureError:
        abort(400)

    except Exception:
        app.logger.error(traceback.format_exc())
        abort(500)

    return "OK"



# =========================================================
# Bot 加入群組：回傳並印出 Group ID
# =========================================================

@handler.add(JoinEvent)
def handle_join(event):
    source = getattr(event, "source", None)
    source_type = getattr(source, "type", None)
    group_id = getattr(source, "group_id", None)
    room_id = getattr(source, "room_id", None)
    conversation_id = group_id or room_id

    if not conversation_id:
        return

    print("=" * 60, flush=True)
    print(f"LINE {source_type or 'conversation'} ID：{conversation_id}", flush=True)
    print("=" * 60, flush=True)
    app.logger.info("Bot joined %s, ID=%s", source_type, conversation_id)

    label = "群組 ID" if group_id else "多人聊天室 ID"
    reply_text(
        event.reply_token,
        f"Bot 已成功加入！\n\nLINE {label}：\n{conversation_id}\n\n請複製這組 ID，回到 Bot 私人聊天室，點擊「家庭群組 ID」完成綁定。",
    )


# =========================================================
# 加入好友
# =========================================================

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = get_user_id(event)

    if not user_id:
        return

    try:
        user = get_user(user_id)

        if not user:
            reply_role_selection(event.reply_token)
            return

        role = user["role"]
        role_setting = ROLE_CONFIG.get(role)

        if not role_setting:
            reply_role_selection(event.reply_token)
            return

        menu_linked = False

        try:
            rich_menu_id = bind_role_rich_menu(
                user_id,
                role,
            )
            menu_linked = True

            if user.get("rich_menu_id") != rich_menu_id:
                save_user(
                    user_id=user_id,
                    display_name=user.get("display_name") or "使用者",
                    role=role,
                    rich_menu_id=rich_menu_id,
                    picture_url=user.get("picture_url"),
                    language=user.get("language"),
                )

        except Exception as error:
            app.logger.error(
                "重新綁定 Rich Menu 失敗：%s",
                error,
            )
            app.logger.error(traceback.format_exc())

        menu_text = (
            "已載入原本的功能選單。"
            if menu_linked
            else "身份資料已恢復，但功能選單尚未載入。"
        )

        reply_text(
            event.reply_token,
            (
                f"{user.get('display_name') or '使用者'}，"
                "歡迎回來！\n"
                f"目前身份：{role_setting['name']}\n"
                f"LINE User ID：{user_id}\n"
                f"{menu_text}"
            ),
        )

    except Exception:
        app.logger.error(traceback.format_exc())


# =========================================================
# 文字訊息
# =========================================================

@handler.add(
    MessageEvent,
    message=TextMessageContent,
)
def handle_text_message(event):
    user_id = get_user_id(event)

    try:
        user = get_user(user_id) if user_id else None

        if user_id and not user:
            reply_role_selection(event.reply_token)
            return

        user_text = (event.message.text or "").strip()

        if user_text == "取消" and user_id:
            clear_operation_state(user_id)
            reply_text(event.reply_token, "已取消本次操作。")
            return

        if user_id and user and user.get("role") == "family":
            if handle_family_text_input(event, user_text, user_id):
                return

        if user and user_text in {
            "重新載入選單",
            "重新綁定選單",
            "載入選單",
        }:
            rich_menu_id = bind_role_rich_menu(
                user_id,
                user["role"],
            )

            save_user(
                user_id=user_id,
                display_name=user.get("display_name") or "使用者",
                role=user["role"],
                rich_menu_id=rich_menu_id,
                picture_url=user.get("picture_url"),
                language=user.get("language"),
            )

            role_name = ROLE_CONFIG.get(
                user["role"],
                {},
            ).get("name", user["role"])

            reply_text(
                event.reply_token,
                (
                    f"已重新載入「{role_name}」專用功能選單。\n"
                    f"LINE User ID：{user_id}"
                ),
            )
            return

        answer = gpt_response(
            user_text
        )

        reply_text(
            event.reply_token,
            answer,
        )

    except Exception as error:
        app.logger.error(traceback.format_exc())

        try:
            reply_text(
                event.reply_token,
                f"系統錯誤：{error}",
            )
        except Exception:
            app.logger.error(traceback.format_exc())


# =========================================================
# 圖片訊息
# =========================================================

@handler.add(
    MessageEvent,
    message=ImageMessageContent,
)
def handle_image_message(event):
    user_id = get_user_id(event)

    try:
        if user_id and not get_user(user_id):
            reply_role_selection(event.reply_token)
            return

        os.makedirs(TMP_DIR, exist_ok=True)

        image_path = os.path.join(
            TMP_DIR,
            f"{event.message.id}.jpg",
        )

        api_client, blob_api = get_blob_api()

        try:
            image_content = blob_api.get_message_content(
                message_id=event.message.id
            )

            with open(image_path, "wb") as image_file:
                image_file.write(image_content)

        finally:
            api_client.close()

        reply_text(
            event.reply_token,
            "已收到藥袋圖片，接下來會進行 AI 辨識。",
        )

    except Exception:
        app.logger.error(traceback.format_exc())

        try:
            reply_text(
                event.reply_token,
                "圖片處理失敗，請稍後再試。",
            )
        except Exception:
            app.logger.error(traceback.format_exc())


# =========================================================
# Postback：身份選擇
# =========================================================

@handler.add(PostbackEvent)
def handle_postback(event):
    try:
        params = parse_qs(
            event.postback.data or ""
        )

        action = params.get(
            "action",
            [None],
        )[0]

        role = params.get(
            "role",
            [None],
        )[0]

        if action in FAMILY_ACTIONS:
            if handle_family_postback(event, action, params):
                return

        if action != "select_role":
            return

        user_id = get_user_id(event)

        if not user_id:
            reply_text(
                event.reply_token,
                "無法取得您的 LINE User ID。",
            )
            return

        existing_user = get_user(user_id)

        if existing_user:
            existing_role = existing_user["role"]
            role_name = ROLE_CONFIG.get(
                existing_role,
                {},
            ).get(
                "name",
                existing_role,
            )

            try:
                rich_menu_id = bind_role_rich_menu(
                    user_id,
                    existing_role,
                )

                save_user(
                    user_id=user_id,
                    display_name=(
                        existing_user.get("display_name")
                        or "使用者"
                    ),
                    role=existing_role,
                    rich_menu_id=rich_menu_id,
                    picture_url=existing_user.get("picture_url"),
                    language=existing_user.get("language"),
                )

                message = (
                    "您的身份已經設定完成。\n"
                    f"目前身份：{role_name}\n"
                    f"LINE User ID：{user_id}\n"
                    "已重新載入專用功能選單。"
                )

            except Exception as error:
                app.logger.error(traceback.format_exc())
                message = (
                    "您的身份已經設定完成。\n"
                    f"目前身份：{role_name}\n"
                    f"LINE User ID：{user_id}\n"
                    "但重新載入功能選單失敗："
                    f"{error}"
                )

            reply_text(
                event.reply_token,
                message,
            )
            return

        if role not in ROLE_CONFIG:
            reply_text(
                event.reply_token,
                "身份資料不正確，請重新操作。",
            )
            return

        role_setting = ROLE_CONFIG[role]
        profile = get_line_profile(user_id)

        display_name = (
            profile.get("display_name")
            or "使用者"
        )

        rich_menu_id = get_role_rich_menu_id(role)

        # 先儲存身份，避免 Rich Menu 綁定失敗時資料遺失
        save_user(
            user_id=user_id,
            display_name=display_name,
            role=role,
            rich_menu_id=rich_menu_id,
            picture_url=profile.get("picture_url"),
            language=profile.get("language"),
        )

        record_role_selection(
            line_user_id=user_id,
            role=role,
        )

        menu_linked = False
        menu_error = None

        try:
            bind_role_rich_menu(
                user_id,
                role,
            )
            menu_linked = True

        except Exception as error:
            menu_error = str(error)
            app.logger.error(
                "Rich Menu 綁定失敗：%s",
                error,
            )
            app.logger.error(traceback.format_exc())

        menu_status = (
            f"已載入「{role_setting['name']}」專用功能選單。"
            if menu_linked
            else (
                "身份已成功儲存，但功能選單載入失敗。\n"
                f"原因：{menu_error or '未知錯誤'}"
            )
        )

        reply_text(
            event.reply_token,
            (
                "身份設定完成！\n\n"
                f"名稱：{display_name}\n"
                f"身份：{role_setting['name']}\n"
                f"LINE User ID：{user_id}\n\n"
                f"{menu_status}"
            ),
        )

    except Exception as error:
        app.logger.error(traceback.format_exc())

        try:
            reply_text(
                event.reply_token,
                f"身份設定失敗：{error}",
            )
        except Exception:
            app.logger.error(traceback.format_exc())


# =========================================================
# 初始化與啟動
# =========================================================

init_database()


if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            5000,
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )
