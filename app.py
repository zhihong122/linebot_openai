from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    TextSendMessage,
    MessageEvent,
    TextMessage,
    PostbackEvent,
    MemberJoinedEvent,
)

import os
import traceback
from openai import OpenAI

app = Flask(__name__)

# LINE Channel settings
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


def gpt_response(text: str) -> str:
    """Call OpenAI and return plain text response."""
    response = client.responses.create(
        model="gpt-5.2-instant",
        input=text,
    )

    answer = response.output_text.strip()
    return answer if answer else "目前沒有產生回覆，請再試一次。"


@app.route("/callback", methods=["POST"])
def callback():
    """Handle LINE webhook callback."""
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    app.logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature.")
        abort(400)
    except Exception:
        app.logger.error("Webhook handle error:\n%s", traceback.format_exc())
        abort(500)

    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """Handle text messages from LINE users."""
    user_text = event.message.text
    app.logger.info("Received LINE text: %s", user_text)

    try:
        answer = gpt_response(user_text)
        app.logger.info("OpenAI answer: %s", answer)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=answer)
        )

    except Exception:
        error_msg = traceback.format_exc()
        app.logger.error("OpenAI/Reply error:\n%s", error_msg)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="目前 AI 回覆失敗，請查看後台 log。")
        )


@handler.add(PostbackEvent)
def handle_postback(event):
    """Handle postback events."""
    app.logger.info("Postback data: %s", event.postback.data)


@handler.add(MemberJoinedEvent)
def welcome_member(event):
    """Welcome a new member joining a group."""
    try:
        uid = event.joined.members[0].user_id
        gid = event.source.group_id
        profile = line_bot_api.get_group_member_profile(gid, uid)
        name = profile.display_name

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{name} 歡迎加入")
        )
    except Exception:
        app.logger.error("Welcome error:\n%s", traceback.format_exc())


if __name__ == "__main__":
    # Optional: quick env check
    if not CHANNEL_ACCESS_TOKEN:
        print("Missing CHANNEL_ACCESS_TOKEN")
    if not CHANNEL_SECRET:
        print("Missing CHANNEL_SECRET")
    if not OPENAI_API_KEY:
        print("Missing OPENAI_API_KEY")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
