# 交通法規問答（Traffic Law RAG）

用白話問台灣交通法規，系統只根據條文回答並標註出處。FastAPI 後端＋React 前端。這是 Leanne 的求職作品集專案。

## 先讀

- `docs/02-implementation-spec.md`：實作規格，唯一依據。依 Step 順序進行，**一次只做一個 Step**。
- `docs/design/README.md`：設計稿對照表、token、畫板不一致時以誰為準。做前端（Step 7–10）前必讀。
- `docs/01-ui-design-brief.md`：設計前的需求簡報，僅供參考，衝突時不以它為準。

## 目前進度

- 已完成：Step 1 專案骨架、Step 2 資料取得與格式確認、Step 3 Chunking 與建索引（Leanne 已檢視；489 chunk、voyage-4、data_version 2026-10-05）
- 已完成：Step 4 檢索與評估集 v0（Leanne 已檢視；40 題已驗證、28 可回答／12 範圍外（q40 改標為可回答，標準答案 `K0040013:39-3`）；baseline 純向量 Recall@5 = 1.000、MRR = 0.845；hybrid 不如純向量，線上用純向量，ADR 0004；單一相似度門檻無法分開貼近主題的範圍外題）
- 已完成：Step 5 生成、引用與拒答（Leanne 已檢視）。模型 `claude-sonnet-5-5`、給模型整條條文、門檻 0.40、改寫預設關閉（ADR 0005）。40 題（28 可回答／12 範圍外）：Recall@5 1.000、MRR 0.845、引用正確率 1.000（精確率 0.653）、數字正確率 1.000、拒答正確率 1.000（範圍外 12/12、誤拒 0/28）。
- 已完成（Leanne 已檢視）：Step 6 SSE 串流 API。`POST /api/ask`（SSE，依 spec 5.3）、`GET /api/chunks/{id}`（含整條 `article_text`）、速率限制（每 IP 每分鐘 10 次）、200 字上限；265 個測試；`curl -N` 已用真實索引與模型驗證一般回答與兩種拒答（ADR 0006）。
- 已完成（待驗收）：Step 7 前端版面骨架、提問與串流答案。token／頁首頁尾／路由、`lib/sse.ts`、問答狀態機（`idle → streaming → done | refused | stopped | error`）、首頁、結果頁骨架、RefusalNotice、ErrorNotice（含速率限制倒數）、關於頁；Vitest 45 個。引用標記與依據卡片此步不可點（Step 8）
- 已完成（待驗收）：Step 8 前端引用、依據與條文全文。全頁唯一的 `activeArticleId`、可點的引用標記與依據卡片（串流中不可點）、桌面下方全文面板（整條 `article_text`）、手機兩個分頁與條文抽屜（上一則／下一則）、引用驗證失敗的虛線 badge 與警告列；Esc 關閉並還原焦點；Vitest 69 個
- 已完成：問題放進網址（spec 5.5-G8 修訂）。`/?q=<問題>` 是結果頁、`/` 是首頁；提問新增瀏覽紀錄，上一頁／下一頁／重新整理／分享連結都會重新提問
- 已完成：亮暗色切換按鈕（主選單最右邊，跟隨系統／亮色／暗色；spec 5.5-G4 修訂）
- 已完成（待 Leanne 檢視）：Step 9 前端檢索過程。PipelineSteps（等待／進行中／完成／略過／相關度不足／已停止）、RetrievalPanel（改寫查詢、名次、分數條、已引用／未引用）、桌面完成時自動收合並可展開、手機預設展開直式列表、拒答頁「為什麼不回答」（拒答分支＋相似度對照條）；Vitest 101 個。**必停檢查點：請對照設計稿（桌面、手機、暗色）後才進 Step 10**
- 已完成（待驗收）：Step 10 評估頁。後端 `GET /api/eval/latest`（讀 `eval/results/latest.json`，由 `run_generation_eval --publish` 產生；逐題結果補上檢索前 5 條與分數）；前端 `/eval`：MetricCard × 5、逐題表格（類別篩選、可展開看標準答案與檢索前 5 筆、符號說明）、手機為卡片列表；頁面數字與 CLI 一致（Recall@5 100%、MRR 0.85、引用／數字／拒答 100%；40 題、範圍外 12 題）。後端測試 284 個、Vitest 111 個。**Step 12 部署要注意：後端映像只複製 `app/`，`eval/results/latest.json` 要另外放進去**
- 已完成（待驗收）：Step 11 測試與品質收尾。後端測試 296 個（補上 Voyage 嵌入客戶端的重試／錯誤處理與來源 IP 判斷）；Playwright E2E 12 個（桌面 10、手機 2）跑在假後端上；CI 新增 e2e job（只在 push 到 main）；README 放了 CI badge（完整 README 是 Step 13）

- 已完成（待驗收）：Step 12 部署。公開網址 https://traffic-law-rag.fly.dev/ （Fly.io，單機，nrt；部署用 `fly deploy --ha=false`）。單一映像（根目錄 `Dockerfile`：前端建置檔由後端一併提供，`STATIC_DIR`）、`fly.toml`、ADR 0007（索引當 artifact 放進映像、單機、手動每月更新）；映像已在本機建置並用真實索引與模型驗證（啟動到 health 約 2.5 秒、記憶體約 200 MB）；每次提問在 log 記 token 用量（`usage run=… input_tokens=… output_tokens=…`，不含問題內容）；CI 新增 `image` job（建映像並 smoke test）。全站每日提問上限 `DAILY_ASK_LIMIT`（預設 300，超過回 503 `daily_limit`，前端有專屬說明）、`max_tokens` 降為 2000；後端測試 308 個、Vitest 113 個。已在公開網址驗證：問答串流、404、速率限制（偽造 X-Forwarded-For 無法繞過）；停機後喚醒第一個請求約 6.5 秒（映像預編譯 `.pyc` 後；之前約 9.7 秒）。

- 已完成（待 Leanne 檢視）：首頁與全文面板的 UI 修正（Main.dc.html 新版）。頁首沒有產品名稱那一列（桌面）、外觀切換在選單右端（GitHub 圖示先隱藏：repo 公開前 `Header.tsx` 的 `SHOW_GITHUB_LINK = false`）、收錄範圍改五欄表格、手機首頁標題與桌面一致、全文面板加「按 Esc 可關閉面板」、輸入框換行時會長高（不再出現多餘捲軸）；另修一個後端問題：兩個請求同時第一次使用時，Chroma 客戶端會同時建立而當掉（500），改成加鎖。法規順序以 `targets.yaml` 為準（處罰條例、安全規則、事故處理辦法、強制險法、裁罰基準；`/api/meta` 排序，頁首深色帶、收錄範圍、拒答頁右欄一致）。後端測試 311 個、Vitest 117 個、E2E 14 個。已於 2026-10-08 重新部署

- 已完成（待 Leanne 驗收）：Step 13 README 與 demo 素材。README 已由 Leanne 改寫（問題與 Input／Output、Mermaid 架構圖、評估結果與限制、技術取捨表連到 ADR、困難與解法、限制、免責與資料授權；原有的部署與成本表移到後段）；`docs/media/demo.gif`（約 31 秒：紅燈右轉、發生車禍時該怎麼辦？兩題成功，公車專用道一題拒答）由 `frontend/scripts/record-demo.mjs`（`pnpm demo:record`，Playwright 錄 webm → ffmpeg → gifski，需 brew 安裝 ffmpeg 與 gifski）在公開網址上錄製。待確認：GitHub 上 Mermaid 圖與 GIF 的渲染、找沒看過專案的人試讀（驗收：三分鐘內理解系統做什麼、好在哪）。

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

- 安裝：`pnpm install`；開發伺服器：`pnpm dev`（`/api` proxy 到 `BACKEND_URL`：環境變數優先，其次 `frontend/.env.local`（不進版控，本機寫 `BACKEND_URL=http://localhost:8021`），預設 `http://localhost:8000`；8000 常被其他專案佔用，連錯時畫面會顯示 HTTP 404）
- 檢查：`pnpm run ci`（Biome）、`pnpm typecheck`（tsc）；測試：`pnpm test`（Vitest）；注意 `pnpm ci` 是 pnpm 內建指令，要用 `pnpm run ci`；E2E：`pnpm e2e`（Playwright，首次要 `pnpm exec playwright install chromium`；會自己啟動假後端 `backend/tests/e2e_server.py` 與前端，不需要金鑰；CI 只在 push 到 main 時跑）

索引（在 `backend/`，需先在 `.env` 設定 `VOYAGE_API_KEY`）：`uv run python -m app.ingestion.build_index`，輸出到 `data/index/`（不進版控）

檢索與評估（在 `backend/`）：`uv run python -m app.pipeline.retrieve "問題" [--mode vector|hybrid|hybrid-bigram]`；`uv run python -m eval.run_eval [--retriever vector|hybrid|hybrid-bigram] --name <檔名>`（輸出 `eval/results/<檔名>.json`，baseline 為 `baseline-vector`）；評估集審核單：`uv run python -m eval.make_review`（產生 `eval/review.md`）

API（在 `backend/`，需 `ANTHROPIC_API_KEY`、`VOYAGE_API_KEY` 與已建好的索引）：`uv run uvicorn app.main:app --port 8021`；`curl -N -X POST localhost:8021/api/ask -H 'Content-Type: application/json' -d '{"question":"紅燈右轉會被罰多少錢？"}'`（本機 8000 常被其他專案佔用，compose 用 8010）

問答與生成評估（在 `backend/`，需 `ANTHROPIC_API_KEY`）：`uv run python -m app.pipeline.answer "問題" [--rewrite]`；`uv run python -m eval.run_generation_eval --name <檔名> [--rewrite] [--refresh] [--publish]`（`--publish` 同時寫成 `eval/results/latest.json`，評估頁 `/api/eval/latest` 顯示的就是這份）（LLM 回應快取在 `data/cache/`）

資料（在 `backend/`）：`uv run python -m app.ingestion.fetch` 下載、`uv run python -m app.ingestion.parse` 解析（說明見 `docs/data-format.md`）

部署（在 repo 根目錄，需先有 `data/index/`）：`docker build -t traffic-law-rag .`；`docker run -p 8031:8000 --env-file .env traffic-law-rag`；上線 `fly deploy --ha=false`（見 README 與 ADR 0007）。

整體：`docker compose up --build`（前端 http://localhost:5173、後端 http://localhost:8010，容器內仍是 8000；本機 8000 常被其他專案佔用）。設定放 `.env`（範本見 `.env.example`）。
