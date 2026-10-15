# ADR 0009：把法規問答與檢索包成 MCP server

狀態：已採用（Step 13 之後的補充）。

## 背景

要讓 Claude Code 在寫程式或讀文件時，能直接查這個專案收錄的交通法規。專案已有完整問答流程（`answer_question`：檢索 → gate → 生成 → 引用／數字驗證）與檢索元件，評估也已量過（Recall@5 1.000、MRR 0.845；生成評估用的就是 `answer_question`），缺的只是對外的介面。

## 選項

| 方案 | 做法 | 結論 |
|---|---|---|
| A. 只暴露檢索 | tool 回傳條文，生成與判斷交給 Claude Code | 只當補充：這個專案的價值在 gate、generate、validate，只給檢索等於把它們丟掉；而且實測「考照報名費」的第一名是 0.49，高於門檻 0.40，單靠分數擋不住範圍外問題（ADR 0004） |
| **B. 包 `answer_question`** | tool 回傳與網站相同流程的答案（已驗證引用與數字）或拒答 | **採用**，作為主要 tool |
| C. 包串流版 `run_ask` | 消化事件流拼回答案 | 不選：事件不含數字驗證結果（只寫 log），要自己拼答案；`answer_question` 才是評估量過的路徑 |
| D. 遠端 HTTP，掛在 Fly 的 app | `/mcp` 端點，免安裝可用 | 暫不做：與網站共用額度並消耗 Voyage／Anthropic 費用，公開前還要補驗證 |

## 決定

- 新增 `backend/app/mcp_server.py`，用官方 MCP Python SDK（`mcp` 2.3.0 的 `MCPServer`），本機 stdio。
- 三個唯讀 tool（`readOnlyHint`）：
  - `ask_traffic_law(question)`：呼叫 `answer_question`，回傳答案（含 `[[article_id]]` 引用標記）、`citations`（法規、條號、`source_url`）、`citations_invalid`、`numbers_unmatched`；拒答時回傳 `refusal_layer`（gate 或 model）與說明。
  - `search_traffic_law(query, k=5)`：只檢索，回傳整條原文、相似度、`source_url`、`amended_date`。
  - `get_article(article_id)`：依 id 取整條。
- 閘門門檻、是否改寫、模型等設定都讀同一份 `Settings`，與網站一致。檢索用 vector（ADR 0004）。
- **答案被長度上限截斷時回錯誤，不當完整答案。** 網站的 `run_ask` 有這個保護，`answer_question` 沒有（它是評估路徑，改它要重跑評估），所以在 MCP 層用一個記錄 `stop_reason` 的 LLM 包裝補上，不動 `answer.py`。
- 依賴組裝（retriever、條文來源、LLM 客戶端）在 `mcp_server.py` 內自己做，沒有抽成與 `api/deps.py` 共用：後者有網站專用的鎖、快取與 `disk_cache=False`，為了這個改它的風險大於重複幾行。
- LLM 客戶端在第一次提問時才建立，沒有 `ANTHROPIC_API_KEY` 時 `ask_traffic_law` 會失敗，但兩個檢索 tool 仍可使用。
- 輸入限制與 `/api/ask` 相同（1–200 字；`k` 為 1–10）。stdout 是協議通道，不可輸出別的東西；logging 走 stderr。
- 回傳的 `notice` 要求 host 原文呈現答案與條號、不改寫金額，`citations_invalid` 或 `numbers_unmatched` 非空要告知使用者。

註冊：

```bash
claude mcp add traffic-law -- uv --directory <repo>/backend run python -m app.mcp_server
```

## 放棄了什麼

- **「與網站逐字相同的答案」**：模型取樣參數無法固定，同一題重跑文字會略有不同；相同的是流程、門檻、prompt 與驗證。
- **對 Claude Code 轉述後的保證**：驗證只保證 tool 回傳的那份答案。Claude Code 之後可能改寫並寫錯金額或引用，只能靠 `notice` 約束，無法強制。
- **網站的速率限制與每日額度**：本機呼叫不經過，花的是自己的 key。
- **遠端版本與驗證**：見選項 D。tool 本身可以原樣重用，之後要做只需換傳輸與加驗證。

## 後果

- 需要本機索引（`data/index/`，不進版控，取得方式見 `docs/operations.md`）、`VOYAGE_API_KEY`；`ask_traffic_law` 另需 `ANTHROPIC_API_KEY`，每題約 US$0.012（README 的粗估，只量過 3 題）、延遲數秒。
- 新增依賴 `mcp`（及其傳遞依賴）。
- 資料版本以 `data_version` 隨每次回傳，host 可據此提示資料可能過時。
- `answer_question` 的行為若改變（prompt、門檻、驗證規則），MCP 的答案會跟著變，不需要另外維護。

## 驗證

- 單元測試（`tests/test_mcp_server.py`）：用假的檢索、條文與 LLM，經 SDK 的記憶體內 Client 呼叫。涵蓋有效答案與引用、無效引用與數字錯誤會被帶出、gate 拒答不呼叫模型、模型拒答、截斷回錯誤、輸入邊界、沒有 API key 時檢索 tool 仍可用、tool 皆唯讀且描述含範圍。
- 實際以 stdio 啟動（真實索引與模型）：
  - 「紅燈右轉會被罰多少錢？」：回答含道交處罰條例第 53、53-1 條，引用皆有效、數字全部對得上。
  - 「考照報名費多少？」（第一名相似度 0.49，通過 gate）：由模型拒答（`refusal_layer = model`）。
  - 「超速罰款是照裁罰基準表的哪一級？」：由模型拒答。
- 尚未做：在 Claude Code 裡的手動場景驗證，以及 Claude Code 轉述答案時是否保留引用與金額。
