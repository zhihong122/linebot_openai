from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

import os
import traceback
from openai import OpenAI

app = Flask(__name__)

# 環境變數
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 初始化
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
client = OpenAI(api_key=OPENAI_API_KEY)


def GPT_response(text):
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=text
    )
    answer = response.output_text.strip()
    return answer


# 監聽 /callback
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. Check your channel secret.")
        abort(400)
    except Exception as e:
        app.logger.error(f"Handler error: {repr(e)}")
        abort(500)

    return 'OK'


# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    msg = event.message.text
    try:
        print(f"User message: {msg}")

        gpt_answer = GPT_response(msg)
        print(f"GPT answer: {gpt_answer}")

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=gpt_answer[:5000])  # LINE文字上限保守處理
        )

    except Exception as e:
        print("=== OpenAI / Reply Error ===")
        print(traceback.format_exc())

        error_msg = f"發生錯誤：{str(e)}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=error_msg[:5000])
        )


# 處理 Postback
@handler.add(PostbackEvent)
def handle_postback(event):
    print("Postback data:", event.postback.data)


# 新成員加入群組歡迎訊息
@handler.add(MemberJoinedEvent)
def welcome(event):
    try:
        uid = event.joined.members[0].user_id
        gid = event.source.group_id
        profile = line_bot_api.get_group_member_profile(gid, uid)
        name = profile.display_name

        message = TextSendMessage(text=f'{name} 歡迎加入')
        line_bot_api.reply_message(event.reply_token, message)

    except Exception:
        print(traceback.format_exc())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
