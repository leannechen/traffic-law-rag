狀態：草稿

# MCP server 驗證步驟：在 Claude Code 裡實測

對應 [ADR 0009](decisions/0009-mcp-server.md)。單元測試與 stdio 實跑已經做過；這份補的是 ADR「尚未做」的部分：在 Claude Code 裡實際使用，並確認它轉述答案時沒有改掉引用與金額。

## 0. 前置

- `data/index/` 存在（取得方式見 `docs/operations.md`）。
- `.env` 有 `VOYAGE_API_KEY` 與 `ANTHROPIC_API_KEY`（`ask_traffic_law` 需要後者）。
- 在**另一個專案或空目錄**開 Claude Code 驗證，不要在這個 repo 裡。這樣才能確認它是靠 MCP 回答，而不是讀專案檔案。

## 1. 註冊與確認連線

```bash
claude mcp add traffic-law -- uv --directory <repo>/backend run python -m app.mcp_server
claude mcp list
```

預期 `traffic-law` 顯示已連線。進入 Claude Code 後輸入 `/mcp`，應看到三個 tool：`ask_traffic_law`、`search_traffic_law`、`get_article`。

連不上時，先在終端機手動執行 `uv --directory <repo>/backend run python -m app.mcp_server`，看有沒有錯誤（缺索引、缺金鑰）。

## 2. 場景驗證

在 Claude Code 裡逐題問，每題檢查「用了哪個 tool」與「答案內容」。

| # | 問題 | 預期 |
|---|---|---|
| 1 | 紅燈右轉會被罰多少錢？ | 呼叫 `ask_traffic_law`；回答含道交處罰條例第 53 條的「六百元以上一千八百元以下」，並提到 53-1（捷運共用路口）的「一千二百元以上三千六百元以下」；有附條號 |
| 2 | 考照報名費多少？ | `ask_traffic_law` 拒答；Claude Code 應說依收錄法規查不到，**不應自己補一個金額** |
| 3 | 超速罰款是照裁罰基準表的哪一級？ | 拒答，或說明裁罰基準的附表沒有收錄；不應編出級距 |
| 4 | 幫我把道交處罰條例第 53 條原文貼出來 | 呼叫 `get_article`（id 為 `K0040012:53`，可能先經 `search_traffic_law`）；原文與資料一致 |
| 5 | 今天天氣如何？ | 不呼叫任何 MCP tool |

#1、#2 的預期來自 stdio 實跑的結果（2026-10-15，`data_version` 2026-10-05）；#3、#4、#5 是預期行為，尚未實測。

## 3. 重點觀察：轉述有沒有走樣

驗證只保證 tool 回傳的那份答案；Claude Code 之後可能改寫。在 #1 特別檢查：

1. 展開 tool 的回傳（Claude Code 按 ctrl+o 看詳細輸出），記下 `answer` 的金額與引用。
2. 對照 Claude Code 最後對你說的話：**金額、期間是否逐字一致**、有沒有保留條號。
3. 追問「所以最多罰多少？」，看它會不會自己加總或換算。內部模型的 prompt 禁止這樣做，但 Claude Code 是另一個模型，要看 `notice` 管不管用。

## 4. 邊界與失敗情境

- **缺金鑰**：暫時把 `.env` 的 `ANTHROPIC_API_KEY` 註解掉，重啟 Claude Code。預期 `ask_traffic_law` 回錯誤，`search_traffic_law` 仍可用。驗完還原。
- **無效輸入**：要求它對超過 200 字的問題呼叫 `ask_traffic_law`，預期回錯誤。
- **用量**：問完幾題後到 Anthropic 與 Voyage 的 usage 頁，確認花費與預期相符（每題約 US$0.012，只量過 3 題的粗估）。

## 5. 通過標準

- 場景 1–4 行為如預期，且場景 2 沒有被 Claude Code「補答案」。
- 轉述時金額與條號沒有被改（輕微改寫但意思一致可接受；金額錯就是不通過）。
- 缺金鑰時檢索 tool 仍可用。

## 6. 結果怎麼處理

- **全部通過**：把結果記進 ADR 0009 的「驗證」段，把「尚未做」那條改成實測結果。
- **轉述走樣**：先調整 `mcp_server.py` 的 `ASK_NOTICE` 與 tool 描述措辭，重測 #1；仍不行再考慮改變 `answer` 的回傳格式，讓它更不易被改寫。
- **場景 2 被補答案**：代表 `notice` 對 host 的約束不夠，要加強 `refusal_message`。

## 驗證紀錄

| 日期 | # | 用了哪個 tool | 結果 | 備註 |
|---|---|---|---|---|
| 2026-10-15 | 1 | `ask_traffic_law` | 通過 | `data_version` 2026-10-05。回傳含第 53 條「六百元以上一千八百元以下」與 53-1「一千二百元以上三千六百元以下」，轉述保留條號與金額數值，但把中文數字改成阿拉伯數字（600、1,800 等），數值一致。我另外問了汽車與機車，tool 說條文沒有機車規定，Claude Code 照實說查不到機車金額。未做 ctrl+o 對照原始回傳，也未做「最多罰多少」追問（第 3 節 2、3 項未測）。 |
| 2026-10-15 | 2 | `ask_traffic_law` | 通過（有保留） | tool 回 `refused: true`（`top_score` 0.6222）。Claude Code 說查不到，沒有補金額。保留：它補了一句「應該是由監理機關另外公告」並建議去監理服務網，這是模型自己的推測，不是 tool 回的內容；沒有給金額。 |
| 2026-10-15 | 3 | `ask_traffic_law` | 通過（有保留） | tool 回 `refused: true`（`top_score` 0.6186）。送出的問法與表上不同（改成「依裁罰基準表怎麼分級？超過規定最高時速多少罰多少？」）。Claude Code 說附表未收錄，沒有編級距。保留：它另外提到第 43 條「超速 60 公里以上加重處罰」，這來自模型記憶，不是 tool 回傳，也沒有查證。 |
| 2026-10-15 | 4 | `get_article` | 通過（有保留） | 第一次呼叫帶了 `law`、`article_no`，參數驗證失敗（`article_id` 必填）：那時 tool schema 還沒載入，我是猜的參數。第二次用 `article_id` = `K0040012:53` 成功，沒有先經 `search_traffic_law`。回傳 `amended_date` 20260817，原文逐字貼出，與 tool 回傳一致。保留：只對照 tool 回傳，沒有另外對照全國法規資料庫。 |
| 2026-10-15 | 5 | 無 | 通過 | 沒有呼叫任何 MCP tool，也沒有呼叫其他工具；回答沒有天氣資料，並請對方提供城市。 |

尚未驗證：第 4 節三項邊界與失敗情境（缺金鑰、超過 200 字、用量），以及第 3 節「最多罰多少」追問。這次是在 `python-for-pros` 專案的 Claude Code session 裡執行，不是這個 repo。
