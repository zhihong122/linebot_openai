from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *

#======python的函數庫==========
import tempfile, os
import datetime
from openai import OpenAI
import time
import traceback
#======python的函數庫==========

app = Flask(__name__)
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')
# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))
# OPENAI API Key初始化設定
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


def GPT_response(text):
    response = client.responses.create(
        prompt={
            "id": "pmpt_69e7a0c125c88193b36b94ee709a31d309f162074e777845",
            "version": "2"
        },
        input=text
    )
    print(response)
    answer = response.output_text.strip()
    return answer
