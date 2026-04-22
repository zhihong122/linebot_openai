from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *

import os
import traceback
from openai import OpenAI

app = Flask(__name__)

static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))

# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def GPT_response(text):
    response = client.responses.create(
        prompt={
            "id": "pmpt_69e7a0c125c88193b36b94ee709a31d309f162074e777845",
            "version": "2"
        },
        input=text
    )
    answer = response.output_text.strip()
    return answer if answer else "目前沒有產生回覆，請再試一次。"


# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception:
        app.logger.error(traceback.format_exc())
        abort(500)

    return 'OK'


# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    msg = event.message.text
    try:
        gpt_answer = GPT_response(msg)
        print(gpt_answer)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=gpt_answer)
        )
    except Exception:
        print(traceback.format_exc())
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='AI 回覆失敗，請查看後台 log。')
        )


# 處理 Postback
@handler.add(PostbackEvent)
def handle_postback(event):
    print(event.postback.data)


# 新成員加入群組
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
