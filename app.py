from flask import Flask, request, abort
import os
import traceback

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    PostbackEvent,
    MemberJoinedEvent,
)

from openai import OpenAI

app = Flask(__name__)

# ===== 環境變數 =====
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("缺少 CHANNEL_ACCESS_TOKEN")
if not CHANNEL_SECRET:
    raise ValueError("缺少 CHANNEL_SECRET")
if not OPENAI_API_KEY:
    raise ValueError("缺少 OPENAI_API_KEY")

# ===== 初始化 =====
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
client = OpenAI(api_key=OPENAI_API_KEY)


def get_messaging_api():
    api_client = ApiClient(configuration)
    return api_client, MessagingApi(api_client)


def safe_text(text: str, limit: int = 5000) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def gpt_response(user_text: str) -> str:
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": "你是一個友善、清楚、簡潔的 LINE 助手，請使用繁體中文回覆。"
            },
            {
                "role": "user",
                "content": user_text
            }
        ]
    )

    answer = getattr(response, "output_text", "").strip()
    if not answer:
        answer = "目前沒有取得回應，請再試一次。"
    return answer


@app.route("/", methods=["GET"])
def home():
    return "LINE Bot is running."


# ===== LINE Webhook =====
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. 請檢查 CHANNEL_SECRET")
        abort(400)
    except Exception:
        app.logger.error(traceback.format_exc())
        abort(500)

    return "OK"


# ===== 收到文字後，呼叫 OpenAI，再 reply_message =====
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_text = event.message.text

    try:
        reply_text = safe_text(gpt_response(user_text))

        api_client, line_bot_api = get_messaging_api()
        try:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        finally:
            api_client.close()

    except Exception as e:
        app.logger.error(traceback.format_exc())

        error_text = safe_text(f"發生錯誤：{str(e)}")
        api_client, line_bot_api = get_messaging_api()
        try:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=error_text)]
                )
            )
        finally:
            api_client.close()


# ===== Postback =====
@handler.add(PostbackEvent)
def handle_postback(event):
    app.logger.info(f"Postback data: {event.postback.data}")


# ===== 有人加入群組 =====
@handler.add(MemberJoinedEvent)
def welcome(event):
    try:
        joined_user_id = event.joined.members[0].user_id
        group_id = event.source.group_id

        api_client, line_bot_api = get_messaging_api()
        try:
            profile = line_bot_api.get_group_member_profile(
                group_id=group_id,
                user_id=joined_user_id
            )

            welcome_text = safe_text(f"{profile.display_name} 歡迎加入")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=welcome_text)]
                )
            )
        finally:
            api_client.close()

    except Exception:
        app.logger.error(traceback.format_exc())


# ===== 主動推播測試：push_message =====
@app.route("/push-test", methods=["GET"])
def push_test():
    user_id = request.args.get("to")
    text = request.args.get("text", "這是一則 push message 測試訊息")

    if not user_id:
        return "請帶 ?to=LINE_USER_ID", 400

    try:
        api_client, line_bot_api = get_messaging_api()
        try:
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=safe_text(text))]
                )
            )
        finally:
            api_client.close()

        return "Push success", 200

    except Exception as e:
        app.logger.error(traceback.format_exc())
        return f"Push failed: {str(e)}", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
