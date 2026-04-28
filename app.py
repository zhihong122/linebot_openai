from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    PostbackEvent,
    MemberJoinedEvent
)

import os
import traceback
from openai import OpenAI

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("缺少 CHANNEL_ACCESS_TOKEN")
if not CHANNEL_SECRET:
    raise ValueError("缺少 CHANNEL_SECRET")
if not OPENAI_API_KEY:
    raise ValueError("缺少 OPENAI_API_KEY")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
client = OpenAI(api_key=OPENAI_API_KEY)


def gpt_response(text: str) -> str:
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=text
    )

    answer = getattr(response, "output_text", "").strip()
    if not answer:
        answer = "目前沒有取得回應，請再試一次。"
    return answer


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. Please check your channel secret.")
        abort(400)
    except Exception as e:
        app.logger.error(f"Webhook handle error: {repr(e)}")
        abort(500)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_text = event.message.text

    try:
        reply_text = gpt_response(user_text)
        if len(reply_text) > 5000:
            reply_text = reply_text[:4990] + "..."

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

    except Exception as e:
        error_detail = traceback.format_exc()
        app.logger.error(error_detail)

        error_text = f"發生錯誤：{str(e)}"
        if len(error_text) > 5000:
            error_text = error_text[:4990] + "..."

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=error_text)]
                )
            )


@handler.add(PostbackEvent)
def handle_postback(event):
    app.logger.info(f"Postback data: {event.postback.data}")


@handler.add(MemberJoinedEvent)
def welcome(event):
    try:
        joined_user_id = event.joined.members[0].user_id
        group_id = event.source.group_id

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            profile = line_bot_api.get_group_member_profile(
                group_id=group_id,
                user_id=joined_user_id
            )

            welcome_text = f"{profile.display_name} 歡迎加入"
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=welcome_text)]
                )
            )
    except Exception:
        app.logger.error(traceback.format_exc())


@app.route("/", methods=["GET"])
def home():
    return "LINE Bot is running."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
