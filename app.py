from flask import Flask, request, abort
import os
import sqlite3
import traceback
from urllib.parse import parse_qs

import requests

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    PushMessageRequest,
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
    MemberJoinedEvent,
    FollowEvent,
    UnfollowEvent,
)

from openai import OpenAI


app = Flask(__name__)


# =========================================================
# 路徑設定
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

static_tmp_path = os.path.join(
    BASE_DIR,
    "static",
    "tmp"
)

local_data_path = os.path.join(
    BASE_DIR,
    "data"
)

SQLITE_DB_PATH = os.path.join(
    local_data_path,
    "line_bot_users.db"
)


# =========================================================
# 環境變數
# =========================================================

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Render PostgreSQL 的 Internal Database URL
DATABASE_URL = os.getenv("DATABASE_URL")

# 三個身份對應的 Rich Menu ID
FAMILY_RICH_MENU_ID = os.getenv("FAMILY_RICH_MENU_ID")
CAREGIVER_RICH_MENU_ID = os.getenv("CAREGIVER_RICH_MENU_ID")
ELDERLY_RICH_MENU_ID = os.getenv("ELDERLY_RICH_MENU_ID")


if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("缺少 CHANNEL_ACCESS_TOKEN")

if not CHANNEL_SECRET:
    raise ValueError("缺少 CHANNEL_SECRET")

if not OPENAI_API_KEY:
    raise ValueError("缺少 OPENAI_API_KEY")


# =========================================================
# 身份設定
# =========================================================

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
# 初始化 LINE 與 OpenAI
# =========================================================

configuration = Configuration(
    access_token=CHANNEL_ACCESS_TOKEN
)

handler = WebhookHandler(
    CHANNEL_SECRET
)

client = OpenAI(
    api_key=OPENAI_API_KEY
)


# =========================================================
# LINE API
# =========================================================

def get_messaging_api():
    api_client = ApiClient(configuration)
    return api_client, MessagingApi(api_client)


def get_blob_api():
    api_client = ApiClient(configuration)
    return api_client, MessagingApiBlob(api_client)


# =========================================================
# 共用函式
# =========================================================

def safe_text(text: str, limit: int = 5000) -> str:
    text = str(text)

    if len(text) <= limit:
        return text

    return text[: limit - 3] + "..."


def get_event_user_id(event):
    """
    從 LINE webhook event 取得 userId。
    """

    source = getattr(event, "source", None)

    if not source:
        return None

    return getattr(source, "user_id", None)


def reply_text_message(reply_token: str, text: str):
    """
    回覆單一文字訊息。
    """

    api_client, line_bot_api = get_messaging_api()

    try:
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text=safe_text(text)
                    )
                ]
            )
        )

    finally:
        api_client.close()


# =========================================================
# 資料庫
# =========================================================

def using_postgresql():
    """
    有 DATABASE_URL 時使用 PostgreSQL。
    沒有時使用本機 SQLite。
    """

    return bool(DATABASE_URL)


def get_database_connection():
    """
    正式 Render 環境使用 PostgreSQL。
    本機測試可使用 SQLite。
    """

    if using_postgresql():
        try:
            import psycopg2
        except ImportError as error:
            raise RuntimeError(
                "使用 PostgreSQL 時需要安裝 psycopg2-binary"
            ) from error

        return psycopg2.connect(
            DATABASE_URL
        )

    os.makedirs(
        local_data_path,
        exist_ok=True
    )

    connection = sqlite3.connect(
        SQLITE_DB_PATH,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_database():
    """
    建立 LINE 使用者身份資料表。
    """

    connection = get_database_connection()

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
                    status_message TEXT,
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
                    status_message TEXT,
                    language TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        connection.commit()

        app.logger.info(
            "===== line_users table initialized ====="
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_user_record(user_id: str):
    """
    依照 LINE userId 查詢身份資料。
    """

    if not user_id:
        return None

    connection = get_database_connection()

    try:
        cursor = connection.cursor()

        if using_postgresql():
            cursor.execute(
                """
                SELECT
                    user_id,
                    display_name,
                    role,
                    rich_menu_id,
                    picture_url,
                    status_message,
                    language,
                    created_at,
                    updated_at
                FROM line_users
                WHERE user_id = %s
                """,
                (user_id,)
            )

        else:
            cursor.execute(
                """
                SELECT
                    user_id,
                    display_name,
                    role,
                    rich_menu_id,
                    picture_url,
                    status_message,
                    language,
                    created_at,
                    updated_at
                FROM line_users
                WHERE user_id = ?
                """,
                (user_id,)
            )

        row = cursor.fetchone()

        if not row:
            return None

        if using_postgresql():
            columns = [
                description[0]
                for description in cursor.description
            ]

            return dict(
                zip(columns, row)
            )

        return dict(row)

    finally:
        connection.close()


def save_user_role(
    user_id: str,
    display_name: str,
    role: str,
    rich_menu_id: str,
    picture_url: str = None,
    status_message: str = None,
    language: str = None,
):
    """
    儲存使用者身份。

    使用者已存在時更新；
    不存在時新增。
    """

    connection = get_database_connection()

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
                    status_message,
                    language
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)

                ON CONFLICT (user_id)
                DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    role = EXCLUDED.role,
                    rich_menu_id = EXCLUDED.rich_menu_id,
                    picture_url = EXCLUDED.picture_url,
                    status_message = EXCLUDED.status_message,
                    language = EXCLUDED.language,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    display_name,
                    role,
                    rich_menu_id,
                    picture_url,
                    status_message,
                    language,
                )
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
                    status_message,
                    language
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    display_name = excluded.display_name,
                    role = excluded.role,
                    rich_menu_id = excluded.rich_menu_id,
                    picture_url = excluded.picture_url,
                    status_message = excluded.status_message,
                    language = excluded.language,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    display_name,
                    role,
                    rich_menu_id,
                    picture_url,
                    status_message,
                    language,
                )
            )

        connection.commit()

        app.logger.info(
            "===== user role saved ===== "
            f"user_id={user_id}, role={role}"
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def delete_user_record(user_id: str) -> bool:
    """
    使用者封鎖 LINE Bot 時，
    刪除其身份紀錄。

    下次解除封鎖時，
    系統就會再次顯示身份選擇。
    """

    if not user_id:
        return False

    connection = get_database_connection()

    try:
        cursor = connection.cursor()

        if using_postgresql():
            cursor.execute(
                """
                DELETE FROM line_users
                WHERE user_id = %s
                """,
                (user_id,)
            )

        else:
            cursor.execute(
                """
                DELETE FROM line_users
                WHERE user_id = ?
                """,
                (user_id,)
            )

        deleted = cursor.rowcount > 0

        connection.commit()

        app.logger.info(
            "===== user record deleted ===== "
            f"user_id={user_id}, deleted={deleted}"
        )

        return deleted

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# 身份選擇訊息
# =========================================================

def create_role_selection_message():
    """
    建立家屬、看護、長者的身份選擇按鈕。
    """

    return TextMessage(
        text=(
            "歡迎使用長照用藥 Bot！\n\n"
            "請先選擇您的身份類別。\n"
            "選擇後，系統會自動載入對應的功能選單。"
        ),
        quick_reply=QuickReply(
            items=[
                QuickReplyItem(
                    action=PostbackAction(
                        label="家屬",
                        data="action=select_role&role=family",
                        display_text="我是家屬"
                    )
                ),

                QuickReplyItem(
                    action=PostbackAction(
                        label="看護",
                        data="action=select_role&role=caregiver",
                        display_text="我是看護"
                    )
                ),

                QuickReplyItem(
                    action=PostbackAction(
                        label="長者",
                        data="action=select_role&role=elderly",
                        display_text="我是長者"
                    )
                ),
            ]
        )
    )


def reply_role_selection(reply_token: str):
    """
    回覆身份選擇訊息。
    """

    api_client, line_bot_api = get_messaging_api()

    try:
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    create_role_selection_message()
                ]
            )
        )

        app.logger.info(
            "===== role selection message sent ====="
        )

    finally:
        api_client.close()


# =========================================================
# LINE Profile
# =========================================================

def get_line_profile(user_id: str):
    """
    取得 LINE 使用者個人資料。
    """

    api_client, line_bot_api = get_messaging_api()

    try:
        profile = line_bot_api.get_profile(
            user_id=user_id
        )

        return {
            "user_id": user_id,

            "display_name": getattr(
                profile,
                "display_name",
                ""
            ),

            "picture_url": getattr(
                profile,
                "picture_url",
                None
            ),

            "status_message": getattr(
                profile,
                "status_message",
                None
            ),

            "language": getattr(
                profile,
                "language",
                None
            ),
        }

    finally:
        api_client.close()


# =========================================================
# Rich Menu 綁定
# =========================================================

def link_rich_menu_to_user(
    user_id: str,
    rich_menu_id: str
):
    """
    將指定 Rich Menu 綁定給指定使用者。
    """

    if not user_id:
        raise ValueError(
            "缺少 LINE userId"
        )

    if not rich_menu_id:
        raise ValueError(
            "該身份尚未設定 Rich Menu ID，"
            "請檢查 Render 環境變數。"
        )

    url = (
        "https://api.line.me/v2/bot/user/"
        f"{user_id}/richmenu/{rich_menu_id}"
    )

    headers = {
        "Authorization": (
            f"Bearer {CHANNEL_ACCESS_TOKEN}"
        )
    }

    response = requests.post(
        url,
        headers=headers,
        timeout=20
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Rich Menu 綁定失敗："
            f"HTTP {response.status_code} "
            f"{response.text}"
        )

    app.logger.info(
        "===== rich menu linked ===== "
        f"user_id={user_id}, "
        f"rich_menu_id={rich_menu_id}"
    )


# =========================================================
# OpenAI
# =========================================================

def gpt_response(user_text: str) -> str:
    app.logger.info(
        "===== before OpenAI call ====="
    )

    app.logger.info(
        f"OPENAI_API_KEY exists: {bool(OPENAI_API_KEY)}"
    )

    app.logger.info(
        f"user_text: {user_text}"
    )

    response = client.responses.create(
        prompt={
            "id": (
                "pmpt_69e86fa11c1c8193bf0389182d0c664c"
                "0cc0ed66294ebdce"
            ),
            "version": "3"
        },
        input=user_text
    )

    answer = getattr(
        response,
        "output_text",
        ""
    ).strip()

    app.logger.info(
        f"===== OpenAI raw output_text ===== {answer}"
    )

    if not answer:
        answer = "目前沒有取得回應，請再試一次。"

    return answer


# =========================================================
# 基本路由
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
        ""
    )

    body = request.get_data(
        as_text=True
    )

    app.logger.info(
        "===== webhook hit ====="
    )

    app.logger.info(
        f"signature exists: {bool(signature)}"
    )

    app.logger.info(
        "Request body: " + body
    )

    try:
        handler.handle(
            body,
            signature
        )

        app.logger.info(
            "===== handler.handle finished ====="
        )

    except InvalidSignatureError:
        app.logger.error(
            "===== InvalidSignatureError ====="
        )

        abort(400)

    except Exception:
        app.logger.error(
            "===== callback exception ====="
        )

        app.logger.error(
            traceback.format_exc()
        )

        abort(500)

    return "OK"


# =========================================================
# 加入好友
# =========================================================

@handler.add(FollowEvent)
def handle_follow(event):
    """
    使用者加入好友或解除封鎖時執行。

    資料庫沒有身份：
        顯示身份選擇。

    資料庫已有身份：
        恢復原本的 Rich Menu。
    """

    app.logger.info(
        "===== FollowEvent triggered ====="
    )

    user_id = get_event_user_id(event)

    if not user_id:
        app.logger.warning(
            "===== FollowEvent has no user_id ====="
        )
        return

    try:
        app.logger.info(
            f"===== Follow user_id: {user_id} ====="
        )

        user_record = get_user_record(
            user_id
        )

        app.logger.info(
            "===== Existing user record ===== "
            f"{user_record}"
        )

        # 沒有身份紀錄，顯示身份選擇
        if not user_record:
            reply_role_selection(
                event.reply_token
            )
            return

        role = user_record.get(
            "role"
        )

        role_setting = ROLE_CONFIG.get(
            role
        )

        # 資料庫身份異常，重新選擇
        if not role_setting:
            reply_role_selection(
                event.reply_token
            )
            return

        rich_menu_id = role_setting.get(
            "rich_menu_id"
        )

        link_rich_menu_to_user(
            user_id=user_id,
            rich_menu_id=rich_menu_id
        )

        display_name = (
            user_record.get("display_name")
            or "使用者"
        )

        reply_text_message(
            event.reply_token,
            (
                f"{display_name}，歡迎回來！\n"
                f"目前身份：{role_setting['name']}\n"
                "已為您載入原本的功能選單。"
            )
        )

    except Exception:
        app.logger.error(
            "===== handle_follow exception ====="
        )

        app.logger.error(
            traceback.format_exc()
        )

        try:
            reply_text_message(
                event.reply_token,
                "系統初始化失敗，請稍後再試。"
            )

        except Exception:
            app.logger.error(
                traceback.format_exc()
            )


# =========================================================
# 使用者封鎖官方帳號
# =========================================================

@handler.add(UnfollowEvent)
def handle_unfollow(event):
    """
    使用者封鎖官方帳號時執行。

    UnfollowEvent 沒有 reply_token，
    所以不能傳訊息給使用者。

    這裡會刪除資料庫中的身份紀錄，
    讓使用者下次解除封鎖後重新選擇身份。
    """

    app.logger.info(
        "===== UnfollowEvent triggered ====="
    )

    user_id = get_event_user_id(event)

    if not user_id:
        app.logger.warning(
            "===== UnfollowEvent has no user_id ====="
        )
        return

    try:
        deleted = delete_user_record(
            user_id
        )

        app.logger.info(
            "===== unfollow cleanup completed ===== "
            f"user_id={user_id}, "
            f"deleted={deleted}"
        )

    except Exception:
        app.logger.error(
            "===== handle_unfollow exception ====="
        )

        app.logger.error(
            traceback.format_exc()
        )


# =========================================================
# 文字訊息
# =========================================================

@handler.add(
    MessageEvent,
    message=TextMessageContent
)
def handle_text_message(event):
    app.logger.info(
        "===== handle_text_message triggered ====="
    )

    app.logger.info(
        f"user text: {event.message.text}"
    )

    app.logger.info(
        f"reply token exists: {bool(event.reply_token)}"
    )

    user_id = get_event_user_id(event)

    try:
        # 私人聊天室中，未設定身份者先選身份
        if user_id:
            user_record = get_user_record(
                user_id
            )

            if not user_record:
                app.logger.info(
                    "===== unregistered user detected ====="
                )

                reply_role_selection(
                    event.reply_token
                )

                return

        reply_text = safe_text(
            gpt_response(
                event.message.text
            )
        )

        app.logger.info(
            f"===== final reply text ===== {reply_text}"
        )

        api_client, line_bot_api = get_messaging_api()

        try:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(
                            text=reply_text
                        )
                    ]
                )
            )

            app.logger.info(
                "===== reply_message sent ====="
            )

        finally:
            api_client.close()

    except Exception as error:
        app.logger.error(
            "===== handle_text_message exception ====="
        )

        app.logger.error(
            traceback.format_exc()
        )

        try:
            reply_text_message(
                event.reply_token,
                safe_text(
                    f"系統錯誤：{str(error)}"
                )
            )

        except Exception:
            app.logger.error(
                traceback.format_exc()
            )


# =========================================================
# 圖片訊息
# =========================================================

@handler.add(
    MessageEvent,
    message=ImageMessageContent
)
def handle_image_message(event):
    app.logger.info(
        "===== handle_image_message triggered ====="
    )

    app.logger.info(
        f"image message id: {event.message.id}"
    )

    user_id = get_event_user_id(event)

    try:
        # 尚未設定身份，不處理圖片
        if user_id:
            user_record = get_user_record(
                user_id
            )

            if not user_record:
                reply_role_selection(
                    event.reply_token
                )

                return

        os.makedirs(
            static_tmp_path,
            exist_ok=True
        )

        image_path = os.path.join(
            static_tmp_path,
            f"{event.message.id}.jpg"
        )

        api_client_blob, blob_api = get_blob_api()

        try:
            message_content = (
                blob_api.get_message_content(
                    message_id=event.message.id
                )
            )

            with open(
                image_path,
                "wb"
            ) as file:
                file.write(
                    message_content
                )

        finally:
            api_client_blob.close()

        reply_text_message(
            event.reply_token,
            "已收到藥袋圖片，接下來會進行 AI 辨識。"
        )

        app.logger.info(
            f"===== image saved: {image_path} ====="
        )

    except Exception:
        app.logger.error(
            "===== handle_image_message exception ====="
        )

        app.logger.error(
            traceback.format_exc()
        )

        try:
            reply_text_message(
                event.reply_token,
                "圖片處理失敗，請查看後台 log。"
            )

        except Exception:
            app.logger.error(
                traceback.format_exc()
            )


# =========================================================
# Postback：身份選擇
# =========================================================

@handler.add(PostbackEvent)
def handle_postback(event):
    app.logger.info(
        "===== PostbackEvent triggered ====="
    )

    postback_data = (
        event.postback.data
        or ""
    )

    app.logger.info(
        f"Postback data: {postback_data}"
    )

    try:
        params = parse_qs(
            postback_data
        )

        action = params.get(
            "action",
            [None]
        )[0]

        role = params.get(
            "role",
            [None]
        )[0]

        # 不是身份選擇事件
        if action != "select_role":
            app.logger.info(
                "===== unrelated postback ignored ====="
            )

            return

        user_id = get_event_user_id(event)

        if not user_id:
            reply_text_message(
                event.reply_token,
                "無法取得您的 LINE User ID。"
            )

            return

        # 防止重複點擊身份按鈕
        existing_user = get_user_record(
            user_id
        )

        if existing_user:
            existing_role = existing_user.get(
                "role"
            )

            existing_role_name = ROLE_CONFIG.get(
                existing_role,
                {}
            ).get(
                "name",
                existing_role
            )

            reply_text_message(
                event.reply_token,
                (
                    "您的身份已經設定完成，"
                    "不需要再次選擇。\n\n"
                    f"目前身份：{existing_role_name}\n"
                    f"LINE User ID：\n{user_id}"
                )
            )

            return

        if role not in ROLE_CONFIG:
            reply_text_message(
                event.reply_token,
                "身份資料不正確，請重新操作。"
            )

            return

        role_setting = ROLE_CONFIG[
            role
        ]

        role_name = role_setting[
            "name"
        ]

        rich_menu_id = role_setting[
            "rich_menu_id"
        ]

        if not rich_menu_id:
            raise ValueError(
                f"{role_name}尚未設定 Rich Menu ID。"
            )

        # 取得 LINE 個人資料
        profile_data = get_line_profile(
            user_id
        )

        display_name = (
            profile_data.get("display_name")
            or "使用者"
        )

        # 綁定身份對應的 Rich Menu
        link_rich_menu_to_user(
            user_id=user_id,
            rich_menu_id=rich_menu_id
        )

        # 儲存身份與個人資料
        save_user_role(
            user_id=user_id,
            display_name=display_name,
            role=role,
            rich_menu_id=rich_menu_id,

            picture_url=profile_data.get(
                "picture_url"
            ),

            status_message=profile_data.get(
                "status_message"
            ),

            language=profile_data.get(
                "language"
            ),
        )

        reply_text_message(
            event.reply_token,
            (
                "身份設定完成！\n\n"
                f"名稱：{display_name}\n"
                f"身份：{role_name}\n"
                f"LINE User ID：\n{user_id}\n\n"
                f"已載入「{role_name}」專用功能選單。"
            )
        )

        app.logger.info(
            "===== role registration completed ===== "
            f"user_id={user_id}, "
            f"role={role}"
        )

    except Exception as error:
        app.logger.error(
            "===== handle_postback exception ====="
        )

        app.logger.error(
            traceback.format_exc()
        )

        try:
            reply_text_message(
                event.reply_token,
                safe_text(
                    f"身份設定失敗：{str(error)}"
                )
            )

        except Exception:
            app.logger.error(
                traceback.format_exc()
            )


# =========================================================
# 有人加入群組
# =========================================================

@handler.add(MemberJoinedEvent)
def welcome(event):
    app.logger.info(
        "===== MemberJoinedEvent triggered ====="
    )

    try:
        joined_user_id = (
            event.joined.members[0].user_id
        )

        group_id = (
            event.source.group_id
        )

        api_client, line_bot_api = get_messaging_api()

        try:
            profile = (
                line_bot_api.get_group_member_profile(
                    group_id=group_id,
                    user_id=joined_user_id
                )
            )

            welcome_text = safe_text(
                f"{profile.display_name} 歡迎加入"
            )

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(
                            text=welcome_text
                        )
                    ]
                )
            )

            app.logger.info(
                "===== welcome reply sent ====="
            )

        finally:
            api_client.close()

    except Exception:
        app.logger.error(
            "===== welcome exception ====="
        )

        app.logger.error(
            traceback.format_exc()
        )


# =========================================================
# 主動推播測試
# =========================================================

@app.route("/test-push", methods=["GET"])
def test_push():
    user_id = request.args.get(
        "to"
    )

    text = request.args.get(
        "text",
        "push 測試成功"
    )

    if not user_id:
        return (
            "請帶 ?to=LINE_USER_ID",
            400
        )

    api_client, line_bot_api = get_messaging_api()

    try:
        line_bot_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[
                    TextMessage(
                        text=safe_text(text)
                    )
                ]
            )
        )

        return "push success", 200

    except Exception as error:
        app.logger.error(
            "===== test_push error ====="
        )

        app.logger.error(
            traceback.format_exc()
        )

        return (
            f"push failed: {str(error)}",
            500
        )

    finally:
        api_client.close()


# =========================================================
# 查詢使用者資料測試
# =========================================================

@app.route("/test-user", methods=["GET"])
def test_user():
    """
    測試：

    /test-user?user_id=Uxxxxxxxx
    """

    user_id = request.args.get(
        "user_id"
    )

    if not user_id:
        return {
            "success": False,
            "message": "請帶入 user_id"
        }, 400

    user_record = get_user_record(
        user_id
    )

    if not user_record:
        return {
            "success": False,
            "message": "找不到使用者"
        }, 404

    for key, value in list(
        user_record.items()
    ):
        if value is not None:
            user_record[key] = str(value)

    return {
        "success": True,
        "user": user_record
    }, 200


# =========================================================
# 手動刪除測試使用者
# =========================================================

@app.route("/test-delete-user", methods=["GET"])
def test_delete_user():
    """
    測試階段手動刪除使用者身份。

    使用方式：

    /test-delete-user?user_id=Uxxxxxxxx

    正式上線前建議刪除這個路由，
    或加入管理員密碼驗證。
    """

    user_id = request.args.get(
        "user_id"
    )

    if not user_id:
        return {
            "success": False,
            "message": "請帶入 user_id"
        }, 400

    try:
        deleted = delete_user_record(
            user_id
        )

        return {
            "success": True,
            "deleted": deleted,
            "user_id": user_id
        }, 200

    except Exception as error:
        app.logger.error(
            traceback.format_exc()
        )

        return {
            "success": False,
            "message": str(error)
        }, 500


# =========================================================
# 初始化資料庫
# =========================================================

try:
    init_database()

except Exception:
    app.logger.error(
        "===== database initialization failed ====="
    )

    app.logger.error(
        traceback.format_exc()
    )

    raise


# =========================================================
# 啟動
# =========================================================

if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
