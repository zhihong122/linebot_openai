from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage, MessageEvent, TextMessage, PostbackEvent, MemberJoinedEvent

import os
import traceback
from openai import OpenAI

app = Flask(__name__)

# LINE
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def GPT_response(text):
    response = client.responses.create(
        model="gpt-4o-mini",
        input=text
    )
    return response.output_text.strip()


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

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
        print("GPT ANSWER:", gpt_answer)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=gpt_answer)
        )
    except Exception as e:
        print("OPENAI ERROR:", repr(e))
        print(traceback.format_exc())

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="系統暫時發生錯誤，請稍後再試")
        )


@handler.add(PostbackEvent)
def handle_postback(event):
    print("POSTBACK DATA:", event.postback.data)


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
