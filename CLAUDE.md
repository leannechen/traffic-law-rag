# 交通法規資料庫（Traffic Law RAG）

用白話問台灣交通法規，系統只根據條文回答並標註出處。FastAPI 後端＋React 前端。給 AI 編程助手與貢獻者看的專案說明；專案介紹請看 [README.md](README.md)。

## 先讀

- `docs/decisions/`：ADR，每個重要技術決定的背景、選項、決定與放棄了什麼。改動前先看相關的那份。
- `docs/design/README.md`：設計稿對照表、token、畫板不一致時以誰為準。改前端前必讀。
- `docs/data-format.md`：資料格式；`docs/operations.md`：部署與維運。
- `docs/archive/`：專案開始前的實作規格與設計簡報，已封存。實際決定以 ADR 為準。

## 目前狀態

規格中的 13 個步驟都已完成並上線（https://traffic-law-rag.fly.dev/ ），push 到 main 由 CI 自動部署（ADR 0008）。

## 工作方式

1. 一次只處理一件事，每個 commit 只放一個主題。
2. 實際情況與文件不符時，先更新相關文件或 ADR，不要自行假設後繼續。
3. 重要技術決策寫成 ADR（背景、選項、決定、放棄了什麼、後果）。
4. 改動 chunking、檢索參數、門檻或 prompt 之後，重跑評估並列出前後數字；數字變差要說明原因。
5. 後端品質靠測試與評估指標（Recall@5、MRR、引用／數字／拒答正確率）把關，不靠逐行 review。

## 不可違反

- 不寫任何抓取 `law.moj.gov.tw` 網頁的程式；資料只來自 data.gov.tw 的開放資料集。
- API key 只放 `.env`，不進程式與版控；`data/raw/` 不進版控。
- 評估集的標準答案（`expected_chunk_ids`、`expected_facts`）只能由人工確認；產生的草稿一律 `verified: false`。
- 前端以核准設計稿為準，要偏離先提出。畫板裡的條文、金額、分數、日期都是示意資料，不可寫進程式或測試。
- 畫面上的產品名稱是「交通法規資料庫」；陰影只用在桌面全文面板；不做 React Flow（見 `docs/archive/implementation-spec.md` 5.5-H）。

## 指令

後端（在 `backend/`）：

- 安裝：`uv sync`
- 開發伺服器：`uv run uvicorn app.main:app --reload`
- 檢查：`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy app tests`
- 測試：`uv run pytest`

前端（在 `frontend/`，pnpm）：

- 安裝：`pnpm install`；開發伺服器：`pnpm dev`（`/api` proxy 到 `BACKEND_URL`：環境變數優先，其次 `frontend/.env.local`（不進版控，本機寫 `BACKEND_URL=http://localhost:8021`），預設 `http://localhost:8000`；8000 常被其他專案佔用，連錯時畫面會顯示 HTTP 404）
- 檢查：`pnpm run ci`（Biome）、`pnpm typecheck`（tsc）；測試：`pnpm test`（Vitest）；注意 `pnpm ci` 是 pnpm 內建指令，要用 `pnpm run ci`；E2E：`pnpm e2e`（Playwright，首次要 `pnpm exec playwright install chromium`；會自己啟動假後端 `backend/tests/e2e_server.py` 與前端，不需要金鑰；CI 只在 push 到 main 時跑）

索引（在 `backend/`，需先在 `.env` 設定 `VOYAGE_API_KEY`）：`uv run python -m app.ingestion.build_index`，輸出到 `data/index/`（不進版控）

檢索與評估（在 `backend/`）：`uv run python -m app.pipeline.retrieve "問題" [--mode vector|hybrid|hybrid-bigram]`；`uv run python -m eval.run_eval [--retriever vector|hybrid|hybrid-bigram] --name <檔名>`（輸出 `eval/results/<檔名>.json`，baseline 為 `baseline-vector`）；評估集審核單：`uv run python -m eval.make_review`（產生 `eval/review.md`）

API（在 `backend/`，需 `ANTHROPIC_API_KEY`、`VOYAGE_API_KEY` 與已建好的索引）：`uv run uvicorn app.main:app --port 8021`；`curl -N -X POST localhost:8021/api/ask -H 'Content-Type: application/json' -d '{"question":"紅燈右轉會被罰多少錢？"}'`（本機 8000 常被其他專案佔用，compose 用 8010）

問答與生成評估（在 `backend/`，需 `ANTHROPIC_API_KEY`）：`uv run python -m app.pipeline.answer "問題" [--rewrite]`；`uv run python -m eval.run_generation_eval --name <檔名> [--rewrite] [--refresh] [--publish]`（`--publish` 同時寫成 `eval/results/latest.json`，評估頁 `/api/eval/latest` 顯示的就是這份）（LLM 回應快取在 `data/cache/`）

資料（在 `backend/`）：`uv run python -m app.ingestion.fetch` 下載、`uv run python -m app.ingestion.parse` 解析（說明見 `docs/data-format.md`）

部署（在 repo 根目錄，需先有 `data/index/`）：`docker build -t traffic-law-rag .`；`docker run -p 8031:8000 --env-file .env traffic-law-rag`；上線：push 到 main 由 CI 自動部署（ADR 0008）；手動備援 `fly deploy --ha=false`。

整體：`docker compose up --build`（前端 http://localhost:5173、後端 http://localhost:8010，容器內仍是 8000；本機 8000 常被其他專案佔用）。設定放 `.env`（範本見 `.env.example`）。
