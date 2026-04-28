# LINE Bot 串 GPT：一鍵可用版

這包專案可以直接部署到 Render，完成 LINE Bot + GPT 回覆。

---

## 你需要準備

1. LINE Developers 的 Messaging API Channel
2. LINE Channel Access Token
3. LINE Channel Secret
4. OpenAI API Key
5. GitHub 帳號
6. Render 帳號

---

## 一、本機測試

### 1. 安裝套件

```bash
pip install -r requirements.txt
```

### 2. 建立 `.env`

把 `.env.example` 複製一份，改名成：

```bash
.env
```

然後填入：

```env
LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_Channel_Access_Token
LINE_CHANNEL_SECRET=你的_LINE_Channel_Secret
OPENAI_API_KEY=你的_OpenAI_API_Key
OPENAI_MODEL=gpt-4.1-mini
```

### 3. 啟動

```bash
uvicorn main:app --reload --port 8000
```

打開：

```txt
http://127.0.0.1:8000
```

看到 `LINE GPT Bot is running` 就代表成功。

---

## 二、用 ngrok 測試 LINE Webhook

```bash
ngrok http 8000
```

你會得到像這樣的網址：

```txt
https://xxxx.ngrok-free.app
```

LINE Developers Webhook URL 填：

```txt
https://xxxx.ngrok-free.app/callback
```

按 Verify。

---

## 三、部署到 Render

### 1. 上傳到 GitHub

建立一個新的 GitHub Repository，把這包檔案全部上傳。

### 2. Render 建立 Web Service

Render 選：

```txt
New → Web Service → Connect GitHub Repository
```

設定：

```txt
Build Command:
pip install -r requirements.txt

Start Command:
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### 3. 加入 Environment Variables

到 Render 的 Environment：

```env
LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_Channel_Access_Token
LINE_CHANNEL_SECRET=你的_LINE_Channel_Secret
OPENAI_API_KEY=你的_OpenAI_API_Key
OPENAI_MODEL=gpt-4.1-mini
```

### 4. 部署完成後

Render 會給你一個網址，例如：

```txt
https://line-gpt-bot.onrender.com
```

LINE Developers Webhook URL 填：

```txt
https://line-gpt-bot.onrender.com/callback
```

---

## 四、LINE Developers 設定

到 Messaging API 頁面：

1. Webhook URL：填入你的 Render 網址 + `/callback`
2. Use webhook：開啟
3. Auto-reply messages：關閉
4. Greeting messages：可關可不關，建議關閉
5. 按 Verify

---

## 五、測試方法

在 LINE 對 Bot 傳：

```txt
測試
```

如果回覆：

```txt
Bot 正常運作中 ✅
```

代表 LINE Bot 正常。

再傳：

```txt
請介紹暨大資管系
```

如果 GPT 有回覆，代表 OpenAI 串接成功。

---

## 六、常見問題

### Verify 失敗

請檢查：

1. Webhook URL 是否有 `/callback`
2. Render 是否成功啟動
3. LINE_CHANNEL_SECRET 是否正確
4. 程式是否有錯誤 Log

### LINE 沒回覆

請檢查：

1. Use webhook 是否開啟
2. Auto-reply 是否關閉
3. Channel Access Token 是否正確
4. Render 免費版是否正在睡眠

### OpenAI 沒回覆

請檢查：

1. OPENAI_API_KEY 是否正確
2. OpenAI 帳戶是否有 API 額度
3. OPENAI_MODEL 是否存在
4. Render Environment Variables 是否有填好

---

## 七、專案檔案說明

```txt
main.py              主程式
requirements.txt    Python 套件
.env.example         環境變數範本
Procfile            部署用
render.yaml          Render 設定參考
README.md            操作教學
```
