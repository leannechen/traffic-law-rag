狀態：草稿

# Step 6 學習筆記：SSE 串流 API

## 這步做了什麼

把問答包成 `POST /api/ask`，用 SSE 一段一段送回去：每個步驟開始與結束（附耗時與一行摘要）、檢索到的條文、答案的逐段文字、引用、驗證結果，最後送 `run.completed`。同時做了 `GET /api/chunks/{id}`（回傳整條條文）、速率限制（超過回 429 加 `Retry-After`）、200 字上限。

**實測**：真實索引與 Sonnet 5.5，第一個字約 1 秒後出現，整個回答約 2.4 秒。範圍外問題被門檻擋下時全程約 0.26 秒，沒有呼叫模型。

## 為什麼這樣選，放棄了什麼

- **用 SSE，不用 WebSocket**：只需要伺服器單向送資料，SSE 就是一個不關閉的 HTTP 回應，簡單、代理比較好處理。放棄了雙向溝通（用不到）。因為要用 POST 帶問題，瀏覽器原生的 `EventSource` 不能用，前端要自己用 `fetch` 讀串流。
- **出錯時送 `error` 事件，不是丟例外**：串流一開始狀態碼就已經是 200，之後出錯無法再改成 500，前端只會看到「連線中斷」。所以改成用事件告知，再正常結束串流。放棄了「讓 HTTP 狀態碼反映一切」的簡單。
- **事件產生器寫成同步的，在執行緒池逐個取**：Claude 的 SDK 與向量庫都是同步的，直接在非同步程式裡呼叫會卡住整個伺服器。放棄了全面改寫成非同步。代價是每個進行中的串流佔一個執行緒。
- **引用標記的解析寫成小型狀態機**：模型一段一段吐字，`[[K0040012:53]]` 可能被切在中間。標記沒收完整就先暫存，確保送出的文字不會有半個標記。放棄了「把切點問題丟給前端」。
- **速率限制先做在記憶體裡**：單一實例夠用、不用多裝東西。放棄了多實例部署時的正確性（要改成共用儲存）。

## 什麼情況會壞

- **經過會「緩衝」的代理**（例如設定不當的 nginx）：事件會等到最後才一次送出，失去串流效果。已加 `X-Accel-Buffering: no`，但要等 Step 12 部署時實測。
- **使用者斷線，後端還在付費產生答案**：已處理，斷線時關閉對模型的串流（實測斷線後同一秒內記錄「提早結束」），但正在等模型下一段的那一刻無法立即中斷。
- **同時太多人在用**：每個串流佔一個執行緒（約 40 個上限），超過就要排隊。目前靠每 IP 每分鐘 10 次擋住。
- **多個實例部署時速率限制失效**：計數存在各自的記憶體裡。
- **`X-Forwarded-For` 可被偽造**：所以預設不採信，只有明確設定才讀，而且只取最後一個值。
- **模型說到一半才說要拒答**：已經送出去的字收不回來，會先看到字再看到「拒答」。prompt 要求拒答時只輸出標記，評估中沒出現過。
- **標記解析**只認 `[[…]]`；模型若改用別的引用格式就抓不到（會被驗證步驟看成沒有引用）。

## 自己動手的實驗

在 `backend/` 底下做。先啟動伺服器（需要 `.env` 有 `ANTHROPIC_API_KEY`、`VOYAGE_API_KEY`），再另開一個終端機送請求。`curl -N` 要用**大寫 N**（關閉輸出緩衝，事件才會即時出現；小寫 `-n` 是另一個意思）。

```bash
uv run uvicorn app.main:app --port 8021
```

**1. 看串流**：觀察事件一個一個出現，順序應該是 `run.started` → 各步驟 `step.started`／`step.completed` → `retrieval.results` → 多個 `answer.delta` 與 `answer.citation` → `validate.result` → `run.completed`。

```bash
curl -N -X POST localhost:8021/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"紅燈右轉會被罰多少錢？"}'
```

**2. 看兩種拒答**：兩者事件序列不同，後者多了 generate 步驟。

```bash
# 範圍外：門檻擋下，不呼叫模型，約 0.26 秒，送 answer.refused（low_relevance）
curl -N -X POST localhost:8021/api/ask -H 'Content-Type: application/json' \
  -d '{"question":"今天天氣怎麼樣？"}'

# 通過門檻但條文不足：模型拒答，約 1.7 秒，送 answer.refused（out_of_scope）
curl -N -X POST localhost:8021/api/ask -H 'Content-Type: application/json' \
  -d '{"question":"公車專用道可以走嗎？"}'
```

**3. 試刁鑽輸入**：

```bash
# 超過 200 字 → 422
curl -s -X POST localhost:8021/api/ask -H 'Content-Type: application/json' \
  -d "{\"question\":\"$(printf '字%.0s' {1..201})\"}"

# 空白 → 422
curl -s -X POST localhost:8021/api/ask -H 'Content-Type: application/json' \
  -d '{"question":"   "}'

# 連送 11 次，第 11 次回 429（-i 才看得到 Retry-After 標頭）
for i in {1..11}; do curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8021/api/ask \
  -H 'Content-Type: application/json' -d '{"question":"紅燈右轉會被罰多少錢？"}'; done
```

上面連送 11 次會真的呼叫模型 10 次。只想看 429 的話，用 `RATE_LIMIT_REQUESTS=2 uv run uvicorn app.main:app --port 8021` 啟動，兩次後就會被擋。

**4. 試斷線**：送一個長問題，輸出到一半按 Ctrl+C，看伺服器的 log 有沒有「提早結束」，並確認沒有錯誤堆疊。

```bash
curl -N -X POST localhost:8021/api/ask -H 'Content-Type: application/json' \
  -d '{"question":"酒駕肇事的話，強制險還會賠嗎？罰則又是什麼？"}'
```

**5. 看整條條文**：比較 `text`（這一塊）和 `article_text`（整條）。

```bash
curl localhost:8021/api/chunks/K0040012:35-p2
```

**6. 看測試怎麼測標記切點**：每個切點（把 `[[K…]]` 切在任意位置）都有測試。

```bash
uv run pytest tests/test_stream_parser.py -v
```

## 面試可能被問的 3 個問題

**1. SSE 和一般 API、WebSocket 有什麼不同？為什麼選 SSE？**
一般 API 是請求一次、等完整回應；SSE 是同一個 HTTP 回應不關閉，伺服器邊算邊送事件，單向、格式簡單、瀏覽器與代理都支援。這個場景只需要伺服器往前端送進度與答案，用不到 WebSocket 的雙向。因為要 POST 問題，我讓前端用 `fetch` 加 `ReadableStream` 自己解析，而不是原生的 `EventSource`。

**2. 串流到一半出錯怎麼辦？使用者中途關掉頁面呢？**
出錯：狀態碼早已送出（200），所以不能再改，我改成送一個 `error` 事件、訊息只有固定的中文說明（內部細節只寫 log），然後正常結束串流，前端可以保留已收到的內容並提示不完整。斷線：伺服器在每個事件之間檢查斷線，並在結束時關閉事件產生器，連帶關閉對模型的串流，避免繼續付費。這兩個都有測試（用假的模型故意中途丟錯、提早關閉產生器）。

**3. 怎麼防止別人把你的 API 刷爆？**
三層：問題長度上限 200 字、每個 IP 每分鐘 10 次的速率限制（超過回 429 並附 `Retry-After` 讓前端顯示倒數）、模型逾時 60 秒。我也坦白它的限制：計數存在記憶體只對單一實例有效、沒有身分驗證，擋得住誤用但擋不住有意的分散式濫用；而且預設不信任 `X-Forwarded-For`，因為那個標頭用戶端可以偽造。

## 實驗紀錄
請你自己跑的實驗清單(在 backend/ 底下)                      
1. 看串流:uv run uvicorn app.main:app --port 8021,另一個終端機貼上 CLAUDE.md 的 curl -N 指令,觀察事件逐個出現。
2. 看兩種拒答:問「今天天氣怎麼樣?」和「公車專用道可以走嗎?」,比較事件序列(後者多了 generate 步驟)。
3. 試刁鑽輸入:很長(201 字)、空白、一直重送(第 11 次看 429 與 Retry-After)。         
  ```
  string_too_long
  問題不可為空白
  {"detail":"請求太頻繁，請稍後再試"}%
  ```
4. 試斷線:送一個長問題(例如「酒駕肇事的話,強制險還會賠嗎?罰則又是什麼?」),在輸出一半時按 Ctrl+C,看伺服器 log 有沒有「提早結束」。
有：
```
2026-10-07 14:33:46,973 INFO app.ask run=c4319f073ef5492281cd23374070061f 提早結束（1478 ms）
```
5. 看整條條文:curl localhost:8021/api/chunks/K0040012:35-p2,比較 text(這一塊)和 article_text(整條)。
   - `text`:這一個 chunk 的內容,也就是索引裡實際存的那一塊。
   - `article_text`:這個 chunk 所屬的整條條文,同一條所有 chunk 依序接起來。
   - 第 35 條很長(1,990 字),超過 800 字上限,所以依「項」切成 `K0040012:35-p1` 和 `-p2` 兩塊。查 `-p2` 時,`text` 只有後半段,`article_text` 是整條。沒被切開的條文,兩者內容相同。
   - 為什麼要兩個:檢索用小塊比對,命中比較準;但使用者看出處、模型回答時,只看半條可能漏掉但書或例外,所以給整條。UI 的全文面板也用 `article_text`。
   - 驗證長度與包含關係(預期 `text` 比 `article_text` 短,且後者包含前者):
     ```bash
     curl -s localhost:8021/api/chunks/K0040012:35-p2 | python3 -c "
     import sys, json; d = json.load(sys.stdin)
     print('text', len(d['text']), '字 / article_text', len(d['article_text']), '字')
     print('text 是 article_text 的一段:', d['text'] in d['article_text'])"
     ```
6. 看測試怎麼測標記切點:uv run pytest tests/test_stream_parser.py -v,每個切點(把 [[K…]] 切在任意位置)都有測試。