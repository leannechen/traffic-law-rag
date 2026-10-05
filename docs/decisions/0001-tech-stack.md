# ADR 0001：技術選型

狀態：已採用（Step 1）

## 背景

這是一個以「只根據條文回答並標註出處」為目標的 RAG 問答系統，同時是作品集專案。需要能快速迭代、型別安全、一鍵啟動，且每個選擇都能在面試中說清楚。

## 決定與放棄的選項

| 層 | 採用 | 放棄 | 為什麼 |
|---|---|---|---|
| 後端框架 | FastAPI + Pydantic v2 | Flask、Django | 原生支援 async 與 SSE 串流；Pydantic 模型同時是 API schema 與 `LawChunk` 資料契約 |
| Python 工具 | uv、ruff、mypy strict、pytest | pip + venv、black + flake8 | uv 鎖版本且快；ruff 一個工具取代 lint 與 format；strict 型別在處理 LLM 輸出這種鬆散資料時能先擋錯 |
| 向量庫 | Chroma（本機持久化） | pgvector、託管向量庫 | 資料量只有數千條條文，不需要資料庫服務；部署只有一個 Python 程序。代價是無法與關聯資料做 SQL join，規模變大時要遷移（詳見後續 ADR） |
| LLM／Embedding | 介面（`LLMClient`、`Embedder`）後面接 Claude API 與 API 型 embedding | 在程式中直接呼叫 SDK | 評估與測試可換成假實作；之後換模型不動 pipeline |
| 前端 | React 18 + TypeScript + Vite | Next.js | 不需要 SSR；SSE 由瀏覽器直接 `fetch` 串流 |
| 資料請求 | TanStack Query | 手寫 useEffect + fetch | 快取、重試、載入狀態現成 |
| 前端品質 | Biome、tsc strict、Vitest | ESLint + Prettier | 單一工具取代兩個，設定少；Vitest 與 Vite 共用設定 |
| 本機啟動 | Docker Compose | 手動開兩個終端機 | 一行指令起前後端，部署前就驗證容器可跑 |
| CI | GitHub Actions | — | 後端與前端兩個 job 平行，跑 lint、型別、測試 |

## 後果

- Chroma 與 Biome 的生態都比對手小；遇到冷門問題時資料較少。
- Step 1 的前端容器用 Vite dev server（含 `/api` proxy），方便開發；正式部署的靜態發佈在 Step 12 另行決定。
- 前端使用 React 18，依 spec；Vite 範本預設的 19 已降版。
