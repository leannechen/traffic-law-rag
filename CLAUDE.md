# 交通法規問答（Traffic Law RAG）

用白話問台灣交通法規，系統只根據條文回答並標註出處。FastAPI 後端＋React 前端。這是 Leanne 的求職作品集專案。

## 先讀

- `docs/02-implementation-spec.md`：實作規格，唯一依據。依 Step 順序進行，**一次只做一個 Step**。
- `docs/design/README.md`：設計稿對照表、token、畫板不一致時以誰為準。做前端（Step 7–10）前必讀。
- `docs/01-ui-design-brief.md`：設計前的需求簡報，僅供參考，衝突時不以它為準。

## 目前進度

- 已完成：Step 1 專案骨架、Step 2 資料取得與格式確認
- 下一步：Step 3 Chunking 與建索引（先提計畫並等確認；完成後必停等檢視）

每完成一個 Step 就更新這一段。

## 工作方式

1. 開始一個 Step 前，依下方「Review 強度」決定要不要先提計畫、等不等確認。
2. 只做該 Step 的範圍，不順手做後面的步驟；每個 Step 各自一個 commit。
3. 完成時逐項對照該 Step 的驗收條件，附上實際執行的指令與輸出，並更新本檔的「目前進度」。
4. 實際情況與 spec 不符時，先停下來回報並更新 spec 或 ADR，不自行假設後繼續。
5. 重要技術決策寫成 ADR，放 `docs/decisions/`。Leanne 需要能在面試中說明每個決策，解釋時講清楚「為什麼」與「放棄了什麼」。

## Review 強度與學習流程

不同 Step 的做法不同。完整規則見 spec 7.1。

| Step | 做法 |
|---|---|
| 1、7–12 | **一口氣做**：簡短說明做法後直接實作，不等核准；完成後對照驗收並回報 |
| 2、3 | **先提計畫並等確認**，重點放在資料長什麼樣、怎麼切；用統計輸出與 `docs/data-format.md` 呈現，不要求 Leanne 讀程式碼 |
| 4、5、6 | **學習流程**：先用前端類比解釋核心概念與常見的坑，再提計畫並等確認；完成後給一份「請 Leanne 自己跑的實驗清單」；最後寫 `docs/learning/step-N.md` |
| 13 | Claude Code 起草 README，Leanne 逐段改寫成自己的話 |

**必停的檢查點**：Step 3、4、5、6、9 完成後停下來等 Leanne 檢視，其餘 Step 驗收通過後可接著做下一個 Step。

**不要要求 Leanne 逐行看後端 diff。** 後端品質靠測試、評估指標（Recall@5、MRR、引用／數字／拒答正確率）與獨立 review 把關；改動 chunking、門檻或 prompt 後，都要重跑評估並回報前後數字。

**學習筆記**（Step 2–6）：`docs/learning/step-N.md`，一頁內、白話、不留未解釋的術語，只回答三題：做了什麼、為什麼選這個方法而不是另一個、什麼情況下會壞掉。再加上「面試可能被問的 3 個問題」。你寫的是草稿，檔案開頭標 `狀態：草稿`，Leanne 改寫後才改成 `狀態：已改寫`。

## 不可違反

- 不寫任何抓取 `law.moj.gov.tw` 網頁的程式；資料只來自 data.gov.tw 的開放資料集。
- API key 只放 `.env`，不進程式與版控；`data/raw/` 不進版控。
- 評估集的標準答案（`expected_chunk_ids`、`expected_facts`）只能由 Leanne 人工確認；產生的草稿一律 `verified: false`。
- 前端以核准設計稿為準，要偏離先提出。畫板裡的條文、金額、分數、日期都是示意資料，不可寫進程式或測試。
- 畫面上的產品名稱是「交通法規資料庫」；陰影只用在桌面全文面板；不做 React Flow（見 spec 5.5-H）。

## 指令

後端（在 `backend/`）：

- 安裝：`uv sync`
- 開發伺服器：`uv run uvicorn app.main:app --reload`
- 檢查：`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy app tests`
- 測試：`uv run pytest`

前端（在 `frontend/`，pnpm）：

- 安裝：`pnpm install`；開發伺服器：`pnpm dev`（`/api` proxy 到 `BACKEND_URL`，預設 `http://localhost:8000`）
- 檢查：`pnpm run ci`（Biome）、`pnpm typecheck`（tsc）；測試：`pnpm test`（Vitest）；注意 `pnpm ci` 是 pnpm 內建指令，要用 `pnpm run ci`

資料（在 `backend/`）：`uv run python -m app.ingestion.fetch` 下載、`uv run python -m app.ingestion.parse` 解析（說明見 `docs/data-format.md`）

整體：`docker compose up --build`（前端 http://localhost:5173、後端 http://localhost:8010，容器內仍是 8000；本機 8000 常被其他專案佔用）。設定放 `.env`（範本見 `.env.example`）。
