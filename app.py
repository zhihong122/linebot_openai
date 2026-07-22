from flask import Flask, request, abort
import os
import json
import traceback
import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
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
    DatetimePickerAction,
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
        from psycopg2.extras import register_uuid
    except ImportError as error:
        raise RuntimeError(
            "使用 PostgreSQL 時需安裝 psycopg2-binary"
        ) from error

    # 讓 psycopg2 能直接處理 PostgreSQL UUID 欄位。
    # 否則從資料庫 SELECT 出來的 uuid.UUID 物件再次作為參數寫入時，
    # 會出現：can't adapt type 'UUID'。
    register_uuid()

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
    "family_medication_list",
    "family_medication_correct",
    "family_medication_remaining",
    "family_medication_low",
    "family_medication_bag_records",
    "family_medication_select_patient",
    "family_medication_select_item",
    "family_medication_select_bag",
    "family_medication_confirm_quantity",
    "family_calendar_view",
    "family_calendar_add",
    "family_calendar_edit",
    "family_calendar_delete",
    "family_calendar_reminder",
    "family_calendar_select_patient",
    "family_calendar_select_event",
    "family_calendar_select_edit_field",
    "family_calendar_save_datetime",
    "family_calendar_confirm_delete",
    "family_calendar_enable_reminder",
    "family_calendar_disable_reminder",
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



def datetime_item(label, data, mode="datetime", initial=None, minimum=None, maximum=None):
    kwargs = {"label": label[:20], "data": data, "mode": mode}
    if initial:
        kwargs["initial"] = initial
    if minimum:
        kwargs["min"] = minimum
    if maximum:
        kwargs["max"] = maximum
    return QuickReplyItem(action=DatetimePickerAction(**kwargs))


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
    if state["step"] == "waiting_actual_quantity":
        payload = state.get("payload", {})
        actual_quantity = _parse_numeric_quantity(user_text)
        payload["actual_quantity"] = str(actual_quantity)
        set_operation_state(
            user_id,
            "family_medication_correct",
            "confirm_actual_quantity",
            payload,
        )
        reply_message(
            event.reply_token,
            make_quick_reply_message(
                (
                    f"長者：{payload['patient_name']}\n"
                    f"藥物：{payload['medication_name']}\n"
                    f"系統計算：{_format_quantity(payload['calculated_quantity'])} "
                    f"{payload['quantity_unit']}\n"
                    f"實際剩餘：{_format_quantity(actual_quantity)} "
                    f"{payload['quantity_unit']}\n\n"
                    "確定儲存這次修正？"
                ),
                [
                    postback_item(
                        "確認修正",
                        "action=family_medication_confirm_quantity",
                    ),
                    postback_item("取消", "action=family_cancel"),
                ],
            ),
        )
        return True

    if state["step"] == "waiting_calendar_title":
        payload = state.get("payload", {})
        payload["calendar_title"] = user_text[:255]
        set_operation_state(user_id,"family_calendar_add","waiting_calendar_location",payload)
        reply_text(event.reply_token,
            "請輸入醫院或地點，例如：埔里基督教醫院\n若沒有地點請輸入「未填寫」。")
        return True

    if state["step"] == "waiting_calendar_location":
        payload = state.get("payload", {})
        payload["calendar_location"] = None if user_text in {"未填寫","無","沒有"} else user_text[:500]
        set_operation_state(user_id,"family_calendar_add","calendar_waiting_datetime",payload)
        reply_message(event.reply_token,make_quick_reply_message(
            "請點選預計前往醫院的日期與時間：",
            [
                datetime_item("選擇日期時間",
                    "action=family_calendar_save_datetime&mode=add",
                    mode="datetime",
                    minimum=datetime.now().strftime("%Y-%m-%dT%H:%M")),
                postback_item("取消","action=family_cancel"),
            ]))
        return True

    if state["step"] == "waiting_calendar_edit_title":
        payload = state.get("payload", {})
        update_patient_calendar_event(
            payload["event_id"],payload["patient_id"],"title",user_text[:255])
        clear_operation_state(user_id)
        reply_text(event.reply_token,f"行程名稱已修改為：{user_text[:255]}")
        return True

    if state["step"] == "waiting_calendar_edit_location":
        payload = state.get("payload", {})
        new_location = None if user_text in {"未填寫","無","沒有"} else user_text[:500]
        update_patient_calendar_event(
            payload["event_id"],payload["patient_id"],"location",new_location)
        clear_operation_state(user_id)
        reply_text(event.reply_token,f"行程地點已修改為：{new_location or '未填寫'}")
        return True

    return False


def handle_family_postback(event, action, params):
    if action.startswith("family_calendar_"):
        return handle_family_calendar_postback(event, action, params)

    if action.startswith("family_medication_"):
        return handle_family_medication_postback(event, action, params)

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
        elder_uuid = uuid.UUID(state["payload"]["target_id"])
        bind_member_to_family(family_id,elder_uuid,"elderly",admin_id)
        ensure_patient_for_elder_user(elder_uuid)
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
# 家屬藥物管理
# =========================================================

MEDICATION_ACTION_LABELS = {
    "family_medication_list": "查看藥物",
    "family_medication_correct": "修正藥物",
    "family_medication_remaining": "藥量剩餘",
    "family_medication_low": "藥快用完",
    "family_medication_bag_records": "藥袋紀錄",
}


def _to_decimal(value, default=Decimal("0")):
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _format_quantity(value):
    number = _to_decimal(value)
    if number == number.to_integral():
        return str(int(number))
    return format(number.normalize(), "f")


def _parse_numeric_quantity(text_value):
    match = re.search(r"-?\d+(?:\.\d+)?", str(text_value or ""))
    if not match:
        raise RuntimeError("請輸入數字，例如：27")
    value = Decimal(match.group())
    if value < 0:
        raise RuntimeError("藥物數量不能小於 0")
    return value


def ensure_patient_for_elder_user(elder_user_id):
    """取得長者的 patients.id；家庭新增長者後若尚未建檔就自動建立。"""
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT p.id, p.full_name
            FROM patients p
            WHERE p.linked_user_id = %s
            ORDER BY p.is_active DESC, p.updated_at DESC
            LIMIT 1
            """,
            (elder_user_id,),
        )
        row = cursor.fetchone()
        if row:
            if not row[1]:
                cursor.execute(
                    """
                    UPDATE patients p
                    SET full_name = COALESCE(u.display_name, '未命名長者'),
                        is_active = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    FROM app_users u
                    WHERE p.id = %s AND u.id = %s
                    """,
                    (row[0], elder_user_id),
                )
                connection.commit()
            return row[0]

        cursor.execute(
            "SELECT COALESCE(NULLIF(display_name,''), '未命名長者') FROM app_users WHERE id=%s",
            (elder_user_id,),
        )
        user_row = cursor.fetchone()
        if not user_row:
            raise RuntimeError("找不到長者使用者資料")

        cursor.execute(
            """
            INSERT INTO patients (linked_user_id, full_name, notes, is_active)
            VALUES (%s, %s, '由家庭管理功能自動建立', TRUE)
            RETURNING id
            """,
            (elder_user_id, user_row[0]),
        )
        patient_id = cursor.fetchone()[0]
        connection.commit()
        return patient_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_family_patients(family_id):
    """列出家庭中所有有效長者，以及其 patient_id。"""
    elders = list_family_members(family_id, "elderly")
    result = []
    for elder in elders:
        patient_id = ensure_patient_for_elder_user(elder["id"])
        item = dict(elder)
        item["patient_id"] = patient_id
        result.append(item)
    return result


def get_family_patient(family_id, patient_id):
    for patient in list_family_patients(family_id):
        if str(patient["patient_id"]) == str(patient_id):
            return patient
    return None


def _medication_inventory_values(row, today=None):
    today = today or date.today()
    dispense_date = row.get("dispense_date") or row.get("start_date")
    course_days = row.get("course_days")
    total_quantity = _to_decimal(row.get("total_quantity"))
    dose_per_time = _to_decimal(row.get("dose_per_time"), Decimal("1"))
    times_per_day = _to_decimal(row.get("times_per_day"), Decimal("1"))
    daily_quantity = max(dose_per_time * times_per_day, Decimal("0"))

    if dispense_date and isinstance(dispense_date, datetime):
        dispense_date = dispense_date.date()

    elapsed_days = max((today - dispense_date).days, 0) if dispense_date else 0
    calculated = max(total_quantity - (Decimal(elapsed_days) * daily_quantity), Decimal("0"))

    adjusted_quantity = row.get("adjusted_quantity")
    adjusted_at = row.get("adjusted_at")
    if adjusted_quantity is not None and adjusted_at:
        adjusted_date = adjusted_at.date() if isinstance(adjusted_at, datetime) else adjusted_at
        adjusted_elapsed = max((today - adjusted_date).days, 0)
        remaining = max(
            _to_decimal(adjusted_quantity) - (Decimal(adjusted_elapsed) * daily_quantity),
            Decimal("0"),
        )
        basis = f"人工修正（{adjusted_date}）"
    else:
        remaining = calculated
        basis = "依調劑日期與每日用量計算"

    if course_days and dispense_date:
        expected_end_date = dispense_date + timedelta(days=max(int(course_days) - 1, 0))
    elif row.get("end_date"):
        expected_end_date = row["end_date"]
    elif daily_quantity > 0 and total_quantity > 0 and dispense_date:
        expected_end_date = dispense_date + timedelta(
            days=max(math.ceil(float(total_quantity / daily_quantity)) - 1, 0)
        )
    else:
        expected_end_date = None

    warning_date = expected_end_date - timedelta(days=3) if expected_end_date else None
    days_remaining = (
        math.ceil(float(remaining / daily_quantity))
        if daily_quantity > 0
        else None
    )

    return {
        "dispense_date": dispense_date,
        "course_days": course_days,
        "total_quantity": total_quantity,
        "daily_quantity": daily_quantity,
        "elapsed_days": elapsed_days,
        "remaining": remaining,
        "basis": basis,
        "expected_end_date": expected_end_date,
        "warning_date": warning_date,
        "days_remaining": days_remaining,
    }


def list_patient_medications(patient_id, active_only=True):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                m.id,
                m.medication_name,
                m.generic_name,
                m.dosage,
                m.instructions,
                m.start_date,
                m.end_date,
                m.is_active,
                m.dispense_date,
                m.course_days,
                m.total_quantity,
                m.dose_per_time,
                m.times_per_day,
                m.quantity_unit,
                a.actual_quantity,
                a.created_at
            FROM medications m
            LEFT JOIN LATERAL (
                SELECT actual_quantity, created_at
                FROM medication_inventory_adjustments mia
                WHERE mia.medication_id = m.id
                ORDER BY mia.created_at DESC
                LIMIT 1
            ) a ON TRUE
            WHERE m.patient_id = %s
              AND (%s = FALSE OR m.is_active = TRUE)
            ORDER BY COALESCE(m.dispense_date, m.start_date) DESC NULLS LAST,
                     m.created_at DESC
            """,
            (patient_id, active_only),
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "medication_name": row[1] or "未命名藥物",
                "generic_name": row[2],
                "dosage": row[3],
                "instructions": row[4],
                "start_date": row[5],
                "end_date": row[6],
                "is_active": row[7],
                "dispense_date": row[8],
                "course_days": row[9],
                "total_quantity": row[10],
                "dose_per_time": row[11],
                "times_per_day": row[12],
                "quantity_unit": row[13] or "份",
                "adjusted_quantity": row[14],
                "adjusted_at": row[15],
            })
        return result
    finally:
        connection.close()


def get_patient_medication(patient_id, medication_id):
    for medication in list_patient_medications(patient_id, active_only=False):
        if str(medication["id"]) == str(medication_id):
            return medication
    return None


def save_inventory_adjustment(
    medication_id,
    patient_id,
    adjusted_by,
    calculated_quantity,
    actual_quantity,
    reason="家屬修正實際剩餘數量",
):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO medication_inventory_adjustments (
                medication_id,
                patient_id,
                adjusted_by,
                calculated_quantity,
                actual_quantity,
                quantity_difference,
                reason
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                medication_id,
                patient_id,
                adjusted_by,
                calculated_quantity,
                actual_quantity,
                actual_quantity - calculated_quantity,
                reason,
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_medication_bag_records(patient_id, limit=12):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                s.id,
                s.created_at,
                s.processing_status,
                s.original_text,
                s.parsed_result,
                s.image_path,
                COALESCE(u.display_name, '未知使用者'),
                COALESCE(r.name_zh_tw, r.code, '未知身份')
            FROM ai_medication_scans s
            LEFT JOIN app_users u ON u.id = s.uploaded_by
            LEFT JOIN roles r ON r.id = u.role_id
            WHERE s.patient_id = %s
            ORDER BY s.created_at DESC
            LIMIT %s
            """,
            (patient_id, limit),
        )
        rows = cursor.fetchall()
        return [{
            "id": r[0],
            "created_at": r[1],
            "status": r[2],
            "original_text": r[3],
            "parsed_result": r[4],
            "image_path": r[5],
            "uploader_name": r[6],
            "uploader_role": r[7],
        } for r in rows]
    finally:
        connection.close()


def get_medication_bag_record(patient_id, scan_id):
    records = list_medication_bag_records(patient_id, limit=50)
    for record in records:
        if str(record["id"]) == str(scan_id):
            return record
    return None


def send_patient_selection(event, user_id, action, family_id):
    patients = list_family_patients(family_id)
    if not patients:
        reply_text(event.reply_token, "目前家庭尚未新增任何長者。請先到「家庭管理」新增長者。")
        return True

    set_operation_state(user_id, action, "select_patient", {})
    if len(patients) == 1:
        patient = patients[0]
        return handle_selected_patient(event, user_id, action, patient)

    items = [
        postback_item(
            p["display_name"],
            f"action=family_medication_select_patient&next_action={action}&patient_id={p['patient_id']}",
            f"選擇 {p['display_name']}",
        )
        for p in patients[:12]
    ]
    reply_message(
        event.reply_token,
        make_quick_reply_message(
            f"{MEDICATION_ACTION_LABELS.get(action, '藥物管理')}\n請選擇長者：",
            items,
        ),
    )
    return True


def medication_summary_text(patient, medications):
    if not medications:
        return f"{patient['display_name']}目前沒有使用中的藥物。"

    lines = [f"{patient['display_name']}目前使用中的藥物："]
    for index, medication in enumerate(medications, 1):
        inventory = _medication_inventory_values(medication)
        lines.extend([
            "",
            f"{index}. {medication['medication_name']}",
            f"含量：{medication.get('dosage') or '未標示'}",
            f"用法：{medication.get('instructions') or '未標示'}",
            f"調劑日期：{inventory['dispense_date'] or '未標示'}",
            f"處方天數：{inventory['course_days'] or '未標示'}",
            f"總量：{_format_quantity(inventory['total_quantity'])} {medication['quantity_unit']}",
        ])
    return "\n".join(lines)


def remaining_summary_text(patient, medications, low_only=False):
    lines = [
        (
            f"{patient['display_name']}三天內可能用完的藥物："
            if low_only
            else f"{patient['display_name']}的藥物剩餘："
        )
    ]
    matched = 0
    today = date.today()

    for medication in medications:
        inventory = _medication_inventory_values(medication, today=today)
        low = False
        if inventory["warning_date"] and inventory["expected_end_date"]:
            low = inventory["warning_date"] <= today <= inventory["expected_end_date"]
        if inventory["daily_quantity"] > 0:
            low = low or inventory["remaining"] <= inventory["daily_quantity"] * Decimal("3")

        if low_only and not low:
            continue

        matched += 1
        lines.extend([
            "",
            f"{matched}. {medication['medication_name']}",
            f"目前剩餘：{_format_quantity(inventory['remaining'])} {medication['quantity_unit']}",
            f"每日使用：{_format_quantity(inventory['daily_quantity'])} {medication['quantity_unit']}",
            f"已經過：{inventory['elapsed_days']} 天",
            f"預計用完：{inventory['expected_end_date'] or '無法計算'}",
            f"計算基準：{inventory['basis']}",
        ])
        if inventory["days_remaining"] is not None:
            lines.append(f"預估還可使用：{inventory['days_remaining']} 天")

    if matched == 0:
        return (
            f"{patient['display_name']}目前沒有三天內即將用完的藥物。"
            if low_only
            else f"{patient['display_name']}目前沒有可計算剩餘量的藥物。"
        )
    return "\n".join(lines)


def handle_selected_patient(event, user_id, action, patient):
    patient_id = patient["patient_id"]
    payload = {
        "patient_id": str(patient_id),
        "patient_name": patient["display_name"],
    }

    if action == "family_medication_list":
        clear_operation_state(user_id)
        reply_text(
            event.reply_token,
            medication_summary_text(
                patient,
                list_patient_medications(patient_id, active_only=True),
            ),
        )
        return True

    if action == "family_medication_remaining":
        clear_operation_state(user_id)
        reply_text(
            event.reply_token,
            remaining_summary_text(
                patient,
                list_patient_medications(patient_id, active_only=True),
                low_only=False,
            ),
        )
        return True

    if action == "family_medication_low":
        clear_operation_state(user_id)
        reply_text(
            event.reply_token,
            remaining_summary_text(
                patient,
                list_patient_medications(patient_id, active_only=True),
                low_only=True,
            ),
        )
        return True

    if action == "family_medication_correct":
        medications = list_patient_medications(patient_id, active_only=True)
        if not medications:
            clear_operation_state(user_id)
            reply_text(event.reply_token, f"{patient['display_name']}目前沒有可修正的藥物。")
            return True
        set_operation_state(user_id, action, "select_medication", payload)
        items = [
            postback_item(
                m["medication_name"][:20],
                f"action=family_medication_select_item&medication_id={m['id']}",
            )
            for m in medications[:12]
        ]
        reply_message(
            event.reply_token,
            make_quick_reply_message(
                f"長者：{patient['display_name']}\n請選擇要修正數量的藥物：",
                items,
            ),
        )
        return True

    if action == "family_medication_bag_records":
        records = list_medication_bag_records(patient_id)
        if not records:
            clear_operation_state(user_id)
            reply_text(event.reply_token, f"{patient['display_name']}目前沒有藥袋拍攝紀錄。")
            return True
        set_operation_state(user_id, action, "select_bag_record", payload)
        items = []
        for record in records[:12]:
            created = record["created_at"].strftime("%Y-%m-%d %H:%M")
            items.append(
                postback_item(
                    created[:20],
                    f"action=family_medication_select_bag&scan_id={record['id']}",
                    f"查看 {created}",
                )
            )
        reply_message(
            event.reply_token,
            make_quick_reply_message(
                f"{patient['display_name']}的藥袋紀錄\n請選擇一筆：",
                items,
            ),
        )
        return True

    return False


def handle_family_medication_postback(event, action, params):
    user_id = get_user_id(event)
    if not user_id:
        reply_text(event.reply_token, "無法取得您的 LINE User ID。")
        return True

    family = ensure_family_admin(user_id)
    family_id = family["id"]
    admin_id = family["admin_user_id"]

    if action in MEDICATION_ACTION_LABELS:
        return send_patient_selection(event, user_id, action, family_id)

    if action == "family_medication_select_patient":
        next_action = params.get("next_action", [None])[0]
        patient_id = params.get("patient_id", [None])[0]
        patient = get_family_patient(family_id, patient_id)
        if not patient:
            raise RuntimeError("找不到這位長者，或長者已不在此家庭")
        if next_action not in MEDICATION_ACTION_LABELS:
            raise RuntimeError("藥物功能資料已逾時")
        return handle_selected_patient(event, user_id, next_action, patient)

    if action == "family_medication_select_item":
        state = get_operation_state(user_id)
        medication_id = params.get("medication_id", [None])[0]
        payload = state.get("payload", {}) if state else {}
        patient_id = payload.get("patient_id")
        patient = get_family_patient(family_id, patient_id)
        medication = (
            get_patient_medication(patient_id, medication_id)
            if patient and patient_id
            else None
        )
        if not patient or not medication:
            raise RuntimeError("修正資料已逾時，請重新操作")

        inventory = _medication_inventory_values(medication)
        payload.update({
            "medication_id": str(medication["id"]),
            "medication_name": medication["medication_name"],
            "calculated_quantity": str(inventory["remaining"]),
            "quantity_unit": medication["quantity_unit"],
        })
        set_operation_state(
            user_id,
            "family_medication_correct",
            "waiting_actual_quantity",
            payload,
        )
        reply_text(
            event.reply_token,
            (
                f"長者：{patient['display_name']}\n"
                f"藥物：{medication['medication_name']}\n"
                f"系統計算剩餘：{_format_quantity(inventory['remaining'])} "
                f"{medication['quantity_unit']}\n\n"
                "請輸入實際剩餘數量，例如：27\n"
                "輸入「取消」可結束操作。"
            ),
        )
        return True

    if action == "family_medication_confirm_quantity":
        state = get_operation_state(user_id)
        payload = state.get("payload", {}) if state else {}
        required = {
            "patient_id",
            "medication_id",
            "actual_quantity",
            "calculated_quantity",
        }
        if not required.issubset(payload):
            raise RuntimeError("修正資料已逾時，請重新操作")

        patient = get_family_patient(family_id, payload["patient_id"])
        if not patient:
            raise RuntimeError("找不到這位長者")

        save_inventory_adjustment(
            medication_id=payload["medication_id"],
            patient_id=payload["patient_id"],
            adjusted_by=admin_id,
            calculated_quantity=_to_decimal(payload["calculated_quantity"]),
            actual_quantity=_to_decimal(payload["actual_quantity"]),
        )
        clear_operation_state(user_id)
        reply_text(
            event.reply_token,
            (
                "藥物數量修正完成！\n"
                f"長者：{payload['patient_name']}\n"
                f"藥物：{payload['medication_name']}\n"
                f"原計算：{_format_quantity(payload['calculated_quantity'])} "
                f"{payload['quantity_unit']}\n"
                f"修正後：{_format_quantity(payload['actual_quantity'])} "
                f"{payload['quantity_unit']}"
            ),
        )
        return True

    if action == "family_medication_select_bag":
        state = get_operation_state(user_id)
        payload = state.get("payload", {}) if state else {}
        patient_id = payload.get("patient_id")
        scan_id = params.get("scan_id", [None])[0]
        patient = get_family_patient(family_id, patient_id)
        record = get_medication_bag_record(patient_id, scan_id) if patient else None
        if not patient or not record:
            raise RuntimeError("藥袋紀錄已逾時，請重新操作")

        clear_operation_state(user_id)
        parsed = record.get("parsed_result")
        if parsed:
            details = json.dumps(parsed, ensure_ascii=False, indent=2)
        else:
            details = record.get("original_text") or "未保存辨識內容"

        reply_text(
            event.reply_token,
            (
                f"長者：{patient['display_name']}\n"
                f"拍攝時間：{record['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
                f"上傳者：{record['uploader_name']}（{record['uploader_role']}）\n"
                f"辨識狀態：{record['status']}\n\n"
                f"{details}"
            ),
        )
        return True

    return False


# =========================================================
# 家屬行事曆管理
# =========================================================

CALENDAR_ACTION_LABELS = {
    "family_calendar_view": "查看行事曆",
    "family_calendar_add": "新增行程",
    "family_calendar_edit": "修改行程",
    "family_calendar_delete": "刪除行程",
    "family_calendar_reminder": "回診提醒",
}


def list_patient_calendar_events(patient_id, upcoming_only=True, limit=30):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id,title,description,location,starts_at,ends_at,
                   all_day,event_type,COALESCE(is_active,TRUE)
            FROM calendar_events
            WHERE patient_id=%s
              AND COALESCE(is_active,TRUE)=TRUE
              AND (%s=FALSE OR starts_at >= CURRENT_TIMESTAMP - INTERVAL '1 day')
            ORDER BY starts_at ASC
            LIMIT %s
            """,
            (patient_id, upcoming_only, limit),
        )
        return [{
            "id": r[0], "title": r[1], "description": r[2],
            "location": r[3], "starts_at": r[4], "ends_at": r[5],
            "all_day": r[6], "event_type": r[7], "is_active": r[8],
        } for r in cursor.fetchall()]
    finally:
        connection.close()


def get_patient_calendar_event(patient_id, event_id):
    for item in list_patient_calendar_events(patient_id, upcoming_only=False, limit=100):
        if str(item["id"]) == str(event_id):
            return item
    return None


def create_patient_calendar_event(patient_id,title,description,location,starts_at,created_by,event_type="hospital_visit"):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO calendar_events (
                patient_id,title,description,location,starts_at,ends_at,
                all_day,event_type,created_by,source_type,is_active
            )
            VALUES (%s,%s,%s,%s,%s,%s,FALSE,%s,%s,'manual',TRUE)
            RETURNING id
            """,
            (patient_id,title,description,location,starts_at,
             starts_at + timedelta(hours=1),event_type,created_by),
        )
        event_id = cursor.fetchone()[0]
        connection.commit()
        return event_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_patient_calendar_event(event_id,patient_id,field,value):
    allowed = {"title":"title","location":"location","starts_at":"starts_at"}
    column = allowed.get(field)
    if not column:
        raise RuntimeError("不支援的行事曆修改欄位")
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        if field == "starts_at":
            cursor.execute(
                """
                UPDATE calendar_events
                SET starts_at=%s, ends_at=%s + INTERVAL '1 hour',
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=%s AND patient_id=%s AND COALESCE(is_active,TRUE)=TRUE
                """,
                (value,value,event_id,patient_id),
            )
        else:
            cursor.execute(
                f"""
                UPDATE calendar_events
                SET {column}=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s AND patient_id=%s AND COALESCE(is_active,TRUE)=TRUE
                """,
                (value,event_id,patient_id),
            )
        if cursor.rowcount == 0:
            raise RuntimeError("找不到要修改的行程")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_patient_calendar_event(event_id,patient_id):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE calendar_events
            SET is_active=FALSE, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s AND patient_id=%s AND COALESCE(is_active,TRUE)=TRUE
            """,
            (event_id,patient_id),
        )
        if cursor.rowcount == 0:
            raise RuntimeError("找不到要刪除的行程")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_followup_reminder_setting(patient_id,family_user_id):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT is_enabled,days_before,reminder_time
            FROM followup_reminder_settings
            WHERE patient_id=%s AND family_user_id=%s
            """,
            (patient_id,family_user_id),
        )
        row = cursor.fetchone()
        if not row:
            return {"is_enabled":False,"days_before":3,"reminder_time":"09:00"}
        return {"is_enabled":row[0],"days_before":row[1],"reminder_time":str(row[2])[:5]}
    finally:
        connection.close()


def save_followup_reminder_setting(patient_id,family_user_id,is_enabled,days_before=3,reminder_time="09:00"):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO followup_reminder_settings (
                patient_id,family_user_id,is_enabled,days_before,reminder_time,updated_at
            )
            VALUES (%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
            ON CONFLICT (patient_id,family_user_id)
            DO UPDATE SET is_enabled=EXCLUDED.is_enabled,
                          days_before=EXCLUDED.days_before,
                          reminder_time=EXCLUDED.reminder_time,
                          updated_at=CURRENT_TIMESTAMP
            """,
            (patient_id,family_user_id,is_enabled,days_before,reminder_time),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def calendar_event_text(patient,events):
    if not events:
        return f"{patient['display_name']}目前沒有行事曆行程。"
    lines = [f"{patient['display_name']}的行事曆："]
    for index,item in enumerate(events,1):
        event_name = "原訂回診" if item.get("event_type") == "follow_up" else "自行新增"
        lines.extend([
            "",
            f"{index}. {item['title']}",
            f"時間：{item['starts_at'].strftime('%Y-%m-%d %H:%M')}",
            f"類型：{event_name}",
            f"地點：{item.get('location') or '未填寫'}",
        ])
        if item.get("description"):
            lines.append(f"備註：{item['description']}")
    return "\n".join(lines)


def send_calendar_patient_selection(event,user_id,action,family_id):
    patients = list_family_patients(family_id)
    if not patients:
        reply_text(event.reply_token,"目前家庭尚未新增長者，請先到「家庭管理」新增長者。")
        return True
    if len(patients) == 1:
        return handle_calendar_selected_patient(event,user_id,action,patients[0])
    set_operation_state(user_id,action,"calendar_select_patient",{})
    items = [
        postback_item(
            p["display_name"],
            f"action=family_calendar_select_patient&next_action={action}&patient_id={p['patient_id']}",
            f"選擇 {p['display_name']}",
        )
        for p in patients[:12]
    ]
    reply_message(event.reply_token,make_quick_reply_message(
        f"{CALENDAR_ACTION_LABELS.get(action,'行事曆')}\n請選擇長者：",items))
    return True


def handle_calendar_selected_patient(event,user_id,action,patient):
    patient_id = patient["patient_id"]
    payload = {"patient_id":str(patient_id),"patient_name":patient["display_name"]}

    if action == "family_calendar_view":
        clear_operation_state(user_id)
        reply_text(event.reply_token,calendar_event_text(
            patient,list_patient_calendar_events(patient_id,upcoming_only=False)))
        return True

    if action == "family_calendar_add":
        set_operation_state(user_id,action,"waiting_calendar_title",payload)
        reply_text(event.reply_token,
            f"長者：{patient['display_name']}\n請輸入行程名稱，例如：\n用藥後不舒服回診\n\n輸入「取消」可結束。")
        return True

    if action in {"family_calendar_edit","family_calendar_delete"}:
        events = list_patient_calendar_events(patient_id,upcoming_only=False)
        if not events:
            clear_operation_state(user_id)
            reply_text(event.reply_token,f"{patient['display_name']}目前沒有可操作的行程。")
            return True
        payload["calendar_action"] = action
        set_operation_state(user_id,action,"calendar_select_event",payload)
        items = [
            postback_item(
                f"{item['starts_at'].strftime('%m/%d')} {item['title']}"[:20],
                f"action=family_calendar_select_event&calendar_action={action}&event_id={item['id']}",
            )
            for item in events[:12]
        ]
        verb = "修改" if action == "family_calendar_edit" else "刪除"
        reply_message(event.reply_token,make_quick_reply_message(
            f"長者：{patient['display_name']}\n請選擇要{verb}的行程：",items))
        return True

    if action == "family_calendar_reminder":
        family = ensure_family_admin(user_id)
        setting = get_followup_reminder_setting(patient_id,family["admin_user_id"])
        payload["is_enabled"] = setting["is_enabled"]
        set_operation_state(user_id,action,"calendar_reminder_setting",payload)
        status = "已開啟" if setting["is_enabled"] else "未開啟"
        reply_message(event.reply_token,make_quick_reply_message(
            f"長者：{patient['display_name']}\n回診提醒目前：{status}\n"
            f"預設於回診前 {setting['days_before']} 天 {setting['reminder_time']} 提醒。",
            [
                postback_item("開啟提醒","action=family_calendar_enable_reminder"),
                postback_item("關閉提醒","action=family_calendar_disable_reminder"),
                postback_item("取消","action=family_cancel"),
            ]))
        return True
    return False


def handle_family_calendar_postback(event,action,params):
    user_id = get_user_id(event)
    if not user_id:
        reply_text(event.reply_token,"無法取得您的 LINE User ID。")
        return True
    family = ensure_family_admin(user_id)
    family_id = family["id"]
    admin_id = family["admin_user_id"]

    if action in CALENDAR_ACTION_LABELS:
        return send_calendar_patient_selection(event,user_id,action,family_id)

    if action == "family_calendar_select_patient":
        next_action = params.get("next_action",[None])[0]
        patient_id = params.get("patient_id",[None])[0]
        patient = get_family_patient(family_id,patient_id)
        if not patient:
            raise RuntimeError("找不到這位長者，或長者已不在此家庭")
        if next_action not in CALENDAR_ACTION_LABELS:
            raise RuntimeError("行事曆功能資料已逾時")
        return handle_calendar_selected_patient(event,user_id,next_action,patient)

    if action == "family_calendar_select_event":
        state = get_operation_state(user_id)
        payload = state.get("payload",{}) if state else {}
        patient_id = payload.get("patient_id")
        calendar_action = params.get("calendar_action",[None])[0]
        event_id = params.get("event_id",[None])[0]
        patient = get_family_patient(family_id,patient_id)
        item = get_patient_calendar_event(patient_id,event_id) if patient else None
        if not patient or not item:
            raise RuntimeError("行程資料已逾時，請重新操作")
        payload.update({"event_id":str(item["id"]),"event_title":item["title"]})

        if calendar_action == "family_calendar_delete":
            set_operation_state(user_id,calendar_action,"calendar_confirm_delete",payload)
            reply_message(event.reply_token,make_quick_reply_message(
                f"確定刪除以下行程？\n\n長者：{patient['display_name']}\n"
                f"行程：{item['title']}\n時間：{item['starts_at'].strftime('%Y-%m-%d %H:%M')}",
                [
                    postback_item("確認刪除","action=family_calendar_confirm_delete"),
                    postback_item("取消","action=family_cancel"),
                ]))
            return True

        set_operation_state(user_id,"family_calendar_edit","calendar_select_edit_field",payload)
        reply_message(event.reply_token,make_quick_reply_message(
            f"行程：{item['title']}\n請選擇要修改的內容：",
            [
                postback_item("修改名稱","action=family_calendar_select_edit_field&field=title"),
                postback_item("修改日期時間","action=family_calendar_select_edit_field&field=starts_at"),
                postback_item("修改地點","action=family_calendar_select_edit_field&field=location"),
                postback_item("取消","action=family_cancel"),
            ]))
        return True

    if action == "family_calendar_select_edit_field":
        state = get_operation_state(user_id)
        payload = state.get("payload",{}) if state else {}
        field = params.get("field",[None])[0]
        if not payload.get("event_id"):
            raise RuntimeError("修改資料已逾時，請重新操作")
        if field == "starts_at":
            payload["edit_field"] = field
            set_operation_state(user_id,"family_calendar_edit","calendar_waiting_datetime",payload)
            reply_message(event.reply_token,make_quick_reply_message(
                "請點選新的日期與時間：",
                [
                    datetime_item("選擇日期時間",
                        "action=family_calendar_save_datetime&mode=edit",
                        mode="datetime",
                        minimum=datetime.now().strftime("%Y-%m-%dT%H:%M")),
                    postback_item("取消","action=family_cancel"),
                ]))
            return True
        if field not in {"title","location"}:
            raise RuntimeError("不支援的修改項目")
        payload["edit_field"] = field
        set_operation_state(user_id,"family_calendar_edit",f"waiting_calendar_edit_{field}",payload)
        reply_text(event.reply_token,
            ("請輸入新的行程名稱：" if field == "title" else "請輸入新的地點：")
            + "\n輸入「取消」可結束。")
        return True

    if action == "family_calendar_save_datetime":
        state = get_operation_state(user_id)
        payload = state.get("payload",{}) if state else {}
        dt_value = getattr(getattr(event.postback,"params",None),"datetime",None)
        if not dt_value:
            raise RuntimeError("沒有取得選擇的日期時間")
        selected_dt = datetime.fromisoformat(dt_value)
        mode = params.get("mode",[None])[0]

        if mode == "add":
            required = {"patient_id","calendar_title","calendar_location"}
            if not required.issubset(payload):
                raise RuntimeError("新增行程資料已逾時")
            create_patient_calendar_event(
                payload["patient_id"],payload["calendar_title"],
                payload.get("calendar_description"),payload.get("calendar_location"),
                selected_dt,admin_id)
            clear_operation_state(user_id)
            reply_text(event.reply_token,
                f"行程新增完成！\n長者：{payload['patient_name']}\n"
                f"行程：{payload['calendar_title']}\n"
                f"時間：{selected_dt.strftime('%Y-%m-%d %H:%M')}\n"
                f"地點：{payload.get('calendar_location') or '未填寫'}")
            return True

        if mode == "edit":
            if not payload.get("event_id") or not payload.get("patient_id"):
                raise RuntimeError("修改行程資料已逾時")
            update_patient_calendar_event(
                payload["event_id"],payload["patient_id"],"starts_at",selected_dt)
            clear_operation_state(user_id)
            reply_text(event.reply_token,
                f"行程日期時間修改完成！\n行程：{payload['event_title']}\n"
                f"新時間：{selected_dt.strftime('%Y-%m-%d %H:%M')}")
            return True
        raise RuntimeError("無法判斷日期時間操作")

    if action == "family_calendar_confirm_delete":
        state = get_operation_state(user_id)
        payload = state.get("payload",{}) if state else {}
        if not payload.get("event_id") or not payload.get("patient_id"):
            raise RuntimeError("刪除資料已逾時")
        delete_patient_calendar_event(payload["event_id"],payload["patient_id"])
        clear_operation_state(user_id)
        reply_text(event.reply_token,
            f"已刪除行程：{payload.get('event_title') or '未命名行程'}")
        return True

    if action in {"family_calendar_enable_reminder","family_calendar_disable_reminder"}:
        state = get_operation_state(user_id)
        payload = state.get("payload",{}) if state else {}
        patient_id = payload.get("patient_id")
        if not patient_id or not get_family_patient(family_id,patient_id):
            raise RuntimeError("提醒設定資料已逾時")
        enabled = action == "family_calendar_enable_reminder"
        save_followup_reminder_setting(
            patient_id,admin_id,enabled,days_before=3,reminder_time="09:00")
        clear_operation_state(user_id)
        reply_text(event.reply_token,
            f"{payload.get('patient_name','長者')}的回診提醒已{'開啟' if enabled else '關閉'}。"
            + ("\n系統將在回診日前 3 天上午 09:00 排入通知。" if enabled else ""))
        return True
    return False

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
