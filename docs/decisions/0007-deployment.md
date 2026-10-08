# ADR 0007：部署

狀態：已採用（Step 12）。映像已在本機建置並跑通；Fly.io 上線需要 Leanne 的帳號，實測冷啟動與月成本見 README。

## 背景

要有一個公開 URL。限制：個人作品集、流量很低、不想為閒置付費；線上需要兩把金鑰（Anthropic、Voyage）和 6 MB 的向量索引。

## 決定

| 項目 | 決定 | 放棄了什麼 |
|---|---|---|
| 形態 | **單一映像、單一 URL**：後端（FastAPI）一併提供前端建置檔（`STATIC_DIR`），`/api/*` 之外的路徑回 `index.html` 給 React Router | 前後端分開部署（靜態託管＋API）：要設 CORS，而且 SSE 要跨網域；本專案前端沒有 SSR 或 CDN 需求，單一映像少一個服務、少一類設定錯誤 |
| 索引 | **索引當作 artifact 放進映像**（`COPY data/index`）。索引由本機 `build_index` 產生，不進 git，部署時才進映像 | 在映像建置時重建：建置要帶 Voyage 金鑰、每次部署花 API 費用，且結果可能與評估時的索引不同；把索引 commit 進 git：二進位檔每次重建都增加 repo 大小 |
| 主機 | Fly.io，`shared-cpu-1x`／512 MB，`auto_stop_machines` 沒流量時停機 | 常駐機器：每月固定費用但無冷啟動。作品集流量低，選擇省錢並接受冷啟動 |
| 金鑰 | `fly secrets set`，不寫進映像與 `fly.toml` | |
| 速率限制 | 映像內 `TRUST_PROXY=true`（Fly 代理會帶 `X-Forwarded-For`，只取最後一個值）；仍是單實例、記憶體內計數，所以**只跑一台機器** | 多實例：計數不共享，限制會失效（見 ADR 0006） |
| CORS | 同源不需要；`CORS_ORIGINS=[]` | |
| 評估頁資料 | `backend/eval/results/latest.json` 一併複製進映像（config 的 `REPO_ROOT` 靠映像內目錄結構與 repo 相同：`/app/backend`、`/app/data`） | 執行時重跑評估：要花 API 費用 |

## 後果

- 更新資料的流程是手動、每月一次：重跑 ingestion → `build_index` → `run_generation_eval --publish`（若要更新評估頁）→ `fly deploy`。索引與評估結果因此永遠跟著映像一起版本化。
- 部署必須在**有 `data/index/` 的機器上**做（本機）；CI 不部署，也因此不能在 CI 建這個映像。
- 冷啟動 ＝ 機器啟動 ＋ 第一次請求載入索引與建立客戶端。機器停機時第一個使用者會等比較久。
- 單一機器、單一區域：沒有備援。作品集可以接受。
