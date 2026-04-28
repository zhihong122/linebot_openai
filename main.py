import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException

from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from openai import OpenAI

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="LINE GPT Bot")

if not LINE_CHANNEL_ACCESS_TOKEN:
    logging.warning("LINE_CHANNEL_ACCESS_TOKEN is missing.")
if not LINE_CHANNEL_SECRET:
    logging.warning("LINE_CHANNEL_SECRET is missing.")
if not OPENAI_API_KEY:
    logging.warning("OPENAI_API_KEY is missing.")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai_client = OpenAI(api_key=OPENAI_API_KEY)


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "LINE GPT Bot is running. Webhook path: /callback"
    }


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    body_text = body.decode("utf-8")

    try:
        handler.handle(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logging.exception("Webhook handling failed.")
        raise HTTPException(status_code=500, detail=str(e))

    return "OK"


def ask_gpt(user_text: str) -> str:
    system_prompt = """
你是一個 LINE Bot 助理。
請遵守：
1. 使用繁體中文回答。
2. 回答要自然、親切、簡潔。
3. 如果使用者問程式、學習、生活問題，請用容易懂的方式說明。
4. 不要輸出太長，適合 LINE 閱讀。
"""

    response = openai_client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": system_prompt.strip()
            },
            {
                "role": "user",
                "content": user_text
            }
        ],
    )

    reply = response.output_text.strip()

    # LINE 單則文字訊息上限約 5000 字，這裡保守裁切
    if len(reply) > 4500:
        reply = reply[:4500] + "\n\n（內容較長，已自動截短）"

    return reply


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_text = event.message.text.strip()

    if not user_text:
        reply_text = "我收到空白訊息了，可以再傳一次嗎？"
    elif user_text in ["ping", "Ping", "測試"]:
        reply_text = "Bot 正常運作中 ✅"
    else:
        try:
            reply_text = ask_gpt(user_text)
        except Exception as e:
            logging.exception("OpenAI request failed.")
            reply_text = "抱歉，目前 AI 回覆失敗，請稍後再試。"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )
