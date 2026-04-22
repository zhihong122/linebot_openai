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

# ===== LINE 設定 =====
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# ===== OpenAI 設定 =====
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY 沒有設定")

client = OpenAI(api_key=api_key)


# ===== GPT 回應 =====
def GPT_response(text: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "你是一個友善、簡潔的 LINE 助手。"},
            {"role": "user", "content": text},
        ],
    )
    return response.choices[0].message.content or "我暫時沒有產生回覆。"


# ===== Webhook =====
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


# ===== 文字訊息處理 =====
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    msg = event.message.text

    try:
        gpt_answer = GPT_response(msg)
        print("✅ GPT:", gpt_answer)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=gpt_answer)
        )

    except Exception as e:
        print("🔥 OPENAI ERROR:", repr(e))
        print(traceback.format_exc())

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"錯誤：{str(e)}")
        )


# ===== Postback =====
@handler.add(PostbackEvent)
def handle_postback(event):
    print("POSTBACK:", event.postback.data)


# ===== 加入群組 =====
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


# ===== 啟動 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
