# 藥品 RAG：Render + Mac mini GPT-OSS-20B

- Render：`app.py`、LINE Webhook、`rag` 檢索及 PostgreSQL（資料不搬至 Mac）
- Mac mini：Ollama 執行 `gpt-oss:20b`，只負責 LLM 生成
- Cloudflare Tunnel + Access：讓 Render 安全存取 Mac 的本機 Ollama，**不用開路由器埠**
- CSV 匯入：許可證字號可空、pending 預設可用；參照 `scripts/import_csv.py`。

## 1 Mac 安裝及測試

下載安裝 Ollama：https://ollama.com/download

```bash
ollama pull gpt-oss:20b
ollama run gpt-oss:20b
curl http://127.0.0.1:11434/api/tags
```

16GB 統一記憶體處於模型最低可用條件；建議保持低併發、縮短上下文。Mac 必須保持開機且不睡眠，否則不能回答。

## 2 Cloudflare Tunnel（Mac）

Cloudflare Zero Trust 控制台建立 **Remotely-managed tunnel**；在 Mac 裝 `cloudflared` 並執行控制台提供的 tunnel 安裝/啟動指令。使用一個已託管於 Cloudflare 的網域，建立 public hostname，例如 `llm.example.com`，將 origin service 指向 **`http://127.0.0.1:11434`**。注意：是本機 HTTP，外部為 HTTPS。

在 Cloudflare Access 對 **整個 `llm.example.com/*`** 設立 Self-hosted application，使用 **Service Auth policy** 只允許特定 Service Token。產生 Service Token，將 Client ID 與 Client Secret 存入 Render 的環境變數。不要建立繞過 Access 的 Bypass policy，不要直接將 Ollama 11434 開放外網。Cloudflare 的免費方案與額度請以當下官方控制台為準。

驗證：從非 Mac 網路測試（填真實憑證）：

```bash
curl -fsS 'https://llm.example.com/api/tags' \
  -H 'CF-Access-Client-Id: <client-id>' \
  -H 'CF-Access-Client-Secret: <client-secret>'
```

未帶憑證應被拒絕；帶憑證應回 JSON。Tunnel/Access 設好以前，**Render 不會連通本機 Mac 的 localhost**。

## 3 Render 環境變數

在原本的 Render Web Service 設定：

```env
RAG_CHAT_MODEL=gpt-oss:20b
RAG_CHAT_BASE_URL=https://llm.example.com/v1
RAG_CHAT_API_KEY=ollama
CF_ACCESS_CLIENT_ID=在Cloudflare建立的ID
CF_ACCESS_CLIENT_SECRET=在Cloudflare建立的Secret
RAG_CHAT_TIMEOUT=180
RAG_ENABLE_EMBEDDINGS=false
DATABASE_URL=你的Render資料庫URL
```

`RAG_CHAT_API_KEY=ollama` 僅供 Ollama OpenAI 相容 SDK 的佔位，不是防護；真正驗證是 Cloudflare Access Service Token。`.env` 與 Service Token 都不要 commit 至 GitHub。

## 4 安裝、匯入、接入 LINE

將 `rag/` 放在 `app.py` 同層；`requirements-rag.txt` 內容合併進 Render `requirements.txt`。對既有資料庫執行一次：

```bash
python -m scripts.setup_db
python -m scripts.import_csv data/drug_documents_20261021_083203.csv --no-embeddings
```

匯入由管理端執行一次，**不要每次 Render deploy 或 LINE 訊息到來時重新匯入**。

呼叫介面維持不變：

```python
from rag.service import answer_drug_question
result = answer_drug_question(user_message)
reply_text = result['answer']
```

已包含 `examples/line_webhook_integration.py` 的非侵入式示範。**尚未修改你現有的 app.py**，因為這次未提供最新版本，不能保證目前事件分支與回覆 API 相容。

重要：LINE webhook 應快速回傳 HTTP 200。Mac 上 20B 推論可能耗時，正式整合時將 RAG 放入持久化工作佇列（例如 Redis/RQ），處理完成後使用 LINE push message；不可讓 webhook 同步等候模型，亦不可依賴 Render Web Service 行程內 thread 當作可靠佇列。LINE push message 需依 LINE 官方訊息限制與權限確認。

## 5 排查

- HTTP 403 / HTML login page：Access policy 未允許 service token、hostname 未受完整保護或 credentials 不正確。
- 連線逾時：Mac 睡眠、Ollama 未啟動、Tunnel 中斷或家用網路故障。
- 記憶體不足：縮短檢索段落、降低 Ollama 同時請求數；16GB 裝置不保證流暢。
- 若使用 Cloudflare Access 之服務憑證，SDK 在 `rag/service.py` 以 `default_headers` 發出身份驗證表頭。

此版本已執行 Python 語法與檔案封裝檢查；**未進行真實 Mac、Cloudflare、Render、LINE 端到端連線測試**。藥品資訊仍需保留來源與不確定性提示。
