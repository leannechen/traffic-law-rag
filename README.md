# 交通法規資料庫（Traffic Law RAG）

[![CI](https://github.com/leannechen/traffic-law-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/leannechen/traffic-law-rag/actions/workflows/ci.yml)

用白話問台灣交通法規，系統只根據條文回答，並標註每一句話的出處。FastAPI 後端＋React 前端。

> 這份 README 是 Step 11 暫放的簡版（讓 CI badge 有地方放）；完整的介紹、架構圖、評估結果與技術取捨會在 Step 13 改寫。

## 快速開始

```bash
cp .env.example .env            # 填入 ANTHROPIC_API_KEY、VOYAGE_API_KEY
docker compose up --build       # 前端 http://localhost:5173、後端 http://localhost:8010
```

## 測試

```bash
# 後端（在 backend/）
uv run pytest

# 前端單元測試（在 frontend/）
pnpm test

# 前端 E2E（在 frontend/）：Playwright 驅動真實瀏覽器
pnpm exec playwright install chromium   # 首次才需要
pnpm e2e                                # 跑全部；加 --ui 開互動模式
```

E2E 會自己啟動前端與一個假後端（`backend/tests/e2e_server.py`，模型、檢索、條文都是假資料），不需要 API 金鑰或索引。CI 只在 push 到 main 時跑 E2E。

## 部署（Fly.io）

單一映像，後端一併提供前端（見 [ADR 0007](docs/decisions/0007-deployment.md)）。

```bash
# 首次
fly launch --no-deploy --copy-config
fly secrets set ANTHROPIC_API_KEY=... VOYAGE_API_KEY=...
# 之後每次（需要本機有 data/index/）
fly deploy
```

### 每月更新資料

法規資料來自 data.gov.tw，手動每月更新一次（在 `backend/`）：

```bash
uv run python -m app.ingestion.fetch          # 下載
uv run python -m app.ingestion.parse          # 解析
uv run python -m app.ingestion.build_index    # 重建索引（需要 VOYAGE_API_KEY）
uv run python -m eval.run_generation_eval --name <檔名> --publish   # 選用：更新評估頁
# 回到 repo 根目錄
fly deploy
```

### 冷啟動與成本

| 項目 | 數字 | 來源 |
|---|---|---|
| 容器啟動到 `/api/health` 可用 | 約 2.5 秒 | 本機 Docker 實測 |
| 容器剛啟動後第一次提問 | 約 4.5 秒（含載入索引） | 本機 Docker 實測 |
| Fly 機器從停機喚醒 | 待上線後實測 | — |
| 執行時記憶體 | 約 200 MB（設定 512 MB） | 本機 Docker 實測 |
| 主機費用 | 待確認（常駐 `shared-cpu-1x` 512 MB 約每月數美元；`auto_stop` 沒流量時只付儲存） | 需對照 Fly.io 當下價目 |
| 每次提問的模型費用 | 待估算：實際 token 用量 × Anthropic 當下單價 | 需對照價目 |

開發與測試指令見 [CLAUDE.md](CLAUDE.md)；實作規格見 [docs/02-implementation-spec.md](docs/02-implementation-spec.md)，技術決策見 [docs/decisions/](docs/decisions/)。
