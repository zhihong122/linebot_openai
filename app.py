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
    return text if len(text) <= limit else text[:limit - 3] + "..."


def gpt_response(user_text: str) -> str:
    app.logger.info("===== before OpenAI call =====")
    app.logger.info(f"OPENAI_API_KEY exists: {bool(OPENAI_API_KEY)}")
    app.logger.info(f"user_text: {user_text}")

    response = client.responses.create(
        prompt={
            "id": "pmpt_69e86fa11c1c8193bf0389182d0c664c0cc0ed66294ebdce",
            "version": "3",
            "variables": {
                "user_input": user_text
            }
        }
    )

    answer = getattr(response, "output_text", "").strip()
    app.logger.info(f"===== OpenAI raw output_text ===== {answer}")

    if not answer:
        answer = "OpenAI 有回應，但內容是空的"

    return answer


@app.route("/", methods=["GET"])
def home():
    return "LINE Bot is running."


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    app.logger.info("===== webhook hit =====")
    app.logger.info(f"signature exists: {bool(signature)}")
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
        app.logger.info("===== handler.handle finished =====")
    except InvalidSignatureError:
        app.logger.error("===== InvalidSignatureError =====")
        abort(400)
    except Exception:
        app.logger.error("===== callback exception =====")
        app.logger.error(traceback.format_exc())
        abort(500)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    app.logger.info("===== handle_text_message triggered =====")
    app.logger.info(f"user text: {event.message.text}")
    app.logger.info(f"reply token exists: {bool(event.reply_token)}")

    try:
        reply_text = safe_text(gpt_response(event.message.text))
        app.logger.info(f"===== final reply text ===== {reply_text}")

        api_client, line_bot_api = get_messaging_api()
        try:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
            app.logger.info("===== reply_message sent =====")
        finally:
            api_client.close()

    except Exception as e:
        app.logger.error("===== handle_text_message exception =====")
        app.logger.error(traceback.format_exc())

        error_text = safe_text(f"OpenAI 錯誤：{str(e)}")
        api_client, line_bot_api = get_messaging_api()
        try:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=error_text)]
                )
            )
            app.logger.info("===== error reply sent =====")
        finally:
            api_client.close()


@handler.add(PostbackEvent)
def handle_postback(event):
    app.logger.info("===== PostbackEvent triggered =====")
    app.logger.info(f"Postback data: {event.postback.data}")


@handler.add(MemberJoinedEvent)
def welcome(event):
    app.logger.info("===== MemberJoinedEvent triggered =====")
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
            app.logger.info("===== welcome reply sent =====")
        finally:
            api_client.close()

    except Exception:
        app.logger.error("===== welcome exception =====")
        app.logger.error(traceback.format_exc())


@app.route("/test-push", methods=["GET"])
def test_push():
    user_id = request.args.get("to")
    text = request.args.get("text", "push 測試成功")

    if not user_id:
        return "請帶 ?to=LINE_USER_ID", 400

    api_client, line_bot_api = get_messaging_api()
    try:
        line_bot_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=safe_text(text))]
            )
        )
        return "push success", 200
    except Exception as e:
        app.logger.error("===== test_push error =====")
        app.logger.error(traceback.format_exc())
        return f"push failed: {str(e)}", 500
    finally:
        api_client.close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
