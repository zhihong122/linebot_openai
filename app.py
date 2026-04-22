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

# LINE
channel_access_token = os.getenv("CHANNEL_ACCESS_TOKEN")
channel_secret = os.getenv("CHANNEL_SECRET")
api_key = os.getenv("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")

if not channel_access_token:
    raise RuntimeError("CHANNEL_ACCESS_TOKEN 沒有設定")

if not channel_secret:
    raise RuntimeError("CHANNEL_SECRET 沒有設定")

if not api_key:
    raise RuntimeError("OPENAI_API_KEY 沒有設定")

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)
client = OpenAI(api_key=api_key)

def GPT_response(text):
    response = client.responses.create(
        prompt={
            "id": "pmpt_69e86fa11c1c8193bf0389182d0c664c0cc0ed66294ebdce",
            "version": "1"
        },
        input=text
    )
    return response.output_text


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    msg = event.message.text

    try:
        gpt_answer = GPT_response(msg)
        print("GPT:", gpt_answer)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=gpt_answer)
        )
    except Exception as e:
        print("OPENAI ERROR:", repr(e))
        print(traceback.format_exc())

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"錯誤：{str(e)}")
        )


@handler.add(PostbackEvent)
def handle_postback(event):
    print("POSTBACK:", event.postback.data)


@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"{name}歡迎加入")
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
