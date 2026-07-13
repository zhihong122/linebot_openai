from flask import Flask, request, abort
import os
import sqlite3
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
)


# =========================================================
# Flask 與環境變數
# =========================================================

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

FAMILY_RICH_MENU_ID = (
    os.getenv("FAMILY_RICH_MENU_ID")
    or get_home_rich_menu_id("family")
)

CAREGIVER_RICH_MENU_ID = (
    os.getenv("CAREGIVER_RICH_MENU_ID")
    or get_home_rich_menu_id("caregiver")
)

ELDERLY_RICH_MENU_ID = (
    os.getenv("ELDERLY_RICH_MENU_ID")
    or get_home_rich_menu_id("elderly")
)

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
DATA_DIR = os.path.join(BASE_DIR, "data")
TMP_DIR = os.path.join(BASE_DIR, "static", "tmp")
SQLITE_DB_PATH = os.path.join(DATA_DIR, "line_bot_users.db")

ROLE_CONFIG = {
    "family": {
        "name": "家屬",
        "rich_menu_id": FAMILY_RICH_MENU_ID,
    },
    "caregiver": {
        "name": "看護",
        "rich_menu_id": CAREGIVER_RICH_MENU_ID,
    },
    "elderly": {
        "name": "長者",
        "rich_menu_id": ELDERLY_RICH_MENU_ID,
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
# 資料庫
# =========================================================

def using_postgresql():
    return bool(DATABASE_URL)


def get_db_connection():
    if using_postgresql():
        try:
            import psycopg2
        except ImportError as error:
            raise RuntimeError(
                "使用 PostgreSQL 時需安裝 psycopg2-binary"
            ) from error

        return psycopg2.connect(DATABASE_URL)

    os.makedirs(DATA_DIR, exist_ok=True)

    connection = sqlite3.connect(
        SQLITE_DB_PATH,
        timeout=30,
    )
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        if using_postgresql():
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS line_users (
                    user_id VARCHAR(100) PRIMARY KEY,
                    display_name VARCHAR(255),
                    role VARCHAR(50) NOT NULL,
                    rich_menu_id VARCHAR(255),
                    picture_url TEXT,
                    language VARCHAR(30),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        else:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS line_users (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    role TEXT NOT NULL,
                    rich_menu_id TEXT,
                    picture_url TEXT,
                    language TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_user(user_id):
    if not user_id:
        return None

    connection = get_db_connection()

    try:
        cursor = connection.cursor()
        placeholder = "%s" if using_postgresql() else "?"

        cursor.execute(
            f"""
            SELECT
                user_id,
                display_name,
                role,
                rich_menu_id,
                picture_url,
                language,
                created_at,
                updated_at
            FROM line_users
            WHERE user_id = {placeholder}
            """,
            (user_id,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        if using_postgresql():
            columns = [
                column[0]
                for column in cursor.description
            ]
            return dict(zip(columns, row))

        return dict(row)

    finally:
        connection.close()


def save_user(
    user_id,
    display_name,
    role,
    rich_menu_id=None,
    picture_url=None,
    language=None,
):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        if using_postgresql():
            cursor.execute(
                """
                INSERT INTO line_users (
                    user_id,
                    display_name,
                    role,
                    rich_menu_id,
                    picture_url,
                    language
                )
                VALUES (%s, %s, %s, %s, %s, %s)

                ON CONFLICT (user_id)
                DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    role = EXCLUDED.role,
                    rich_menu_id = EXCLUDED.rich_menu_id,
                    picture_url = EXCLUDED.picture_url,
                    language = EXCLUDED.language,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    display_name,
                    role,
                    rich_menu_id,
                    picture_url,
                    language,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO line_users (
                    user_id,
                    display_name,
                    role,
                    rich_menu_id,
                    picture_url,
                    language
                )
                VALUES (?, ?, ?, ?, ?, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    display_name = excluded.display_name,
                    role = excluded.role,
                    rich_menu_id = excluded.rich_menu_id,
                    picture_url = excluded.picture_url,
                    language = excluded.language,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    display_name,
                    role,
                    rich_menu_id,
                    picture_url,
                    language,
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
    if not rich_menu_id:
        return False

    response = requests.post(
        (
            "https://api.line.me/v2/bot/user/"
            f"{user_id}/richmenu/{rich_menu_id}"
        ),
        headers={
            "Authorization": (
                f"Bearer {CHANNEL_ACCESS_TOKEN}"
            )
        },
        timeout=20,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Rich Menu 綁定失敗："
            f"HTTP {response.status_code} "
            f"{response.text}"
        )

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
    database_name = (
        "PostgreSQL"
        if using_postgresql()
        else "SQLite"
    )

    return (
        "LINE Bot is running. "
        f"Database: {database_name}"
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

        role_setting = ROLE_CONFIG.get(user["role"])

        if not role_setting:
            reply_role_selection(event.reply_token)
            return

        menu_linked = False

        try:
            menu_linked = link_rich_menu(
                user_id,
                role_setting["rich_menu_id"],
            )
        except Exception:
            app.logger.error(
                "重新綁定 Rich Menu 失敗"
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
        if user_id and not get_user(user_id):
            reply_role_selection(event.reply_token)
            return

        answer = gpt_response(
            event.message.text
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
            role_name = ROLE_CONFIG.get(
                existing_user["role"],
                {},
            ).get(
                "name",
                existing_user["role"],
            )

            reply_text(
                event.reply_token,
                (
                    "您的身份已經設定完成。\n"
                    f"目前身份：{role_name}"
                ),
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

        # 先儲存身份，避免 Rich Menu 綁定失敗時資料遺失
        save_user(
            user_id=user_id,
            display_name=display_name,
            role=role,
            rich_menu_id=role_setting["rich_menu_id"],
            picture_url=profile.get("picture_url"),
            language=profile.get("language"),
        )

        menu_linked = False

        try:
            menu_linked = link_rich_menu(
                user_id,
                role_setting["rich_menu_id"],
            )
        except Exception:
            app.logger.error(
                "Rich Menu 綁定失敗"
            )
            app.logger.error(traceback.format_exc())

        menu_status = (
            f"已載入「{role_setting['name']}」專用功能選單。"
            if menu_linked
            else (
                "身份已成功儲存，"
                "但目前尚未載入專用 Rich Menu。"
            )
        )

        reply_text(
            event.reply_token,
            (
                "身份設定完成！\n\n"
                f"名稱：{display_name}\n"
                f"身份：{role_setting['name']}\n\n"
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
