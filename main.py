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
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = "你的 Channel access token"
LINE_CHANNEL_SECRET = "你的 Channel secret"

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


@app.route("/", methods=["GET"])
def home():
    return "LINE Bot is running!"


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=f"測試成功，你剛剛說：{user_text}")
                ]
            )
        )


if __name__ == "__main__":
    app.run()
