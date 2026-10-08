# 維運筆記

線上版：https://traffic-law-rag.fly.dev/（Fly.io，單機，region `nrt`）。決策背景見 [ADR 0007](decisions/0007-deployment.md)。

## 部署

在 repo 根目錄、本機要有 `data/index/`：

```bash
fly deploy --ha=false
```

- **一定要 `--ha=false`**：預設會開兩台。速率限制與每日額度存在各機器的記憶體，兩台會各算各的（額度變兩倍）。已發生過一次，用 `fly scale count 1` 縮回。
- 部署前確認只有一台：`fly status`。
- **不要重跑 `fly launch`**：它會把 `fly.toml` 重寫成單引號並拿掉註解。真的重跑了，把註解補回去。
- 金鑰只在 Fly 上（`fly secrets list` 只看得到名字）。換金鑰：`fly secrets set ANTHROPIC_API_KEY=...`。

## 冷啟動與暖機

- 沒流量約 6 分鐘後機器自動停機；停機後第一個請求約 6.5 秒才回應，之後第一次提問約 4 秒（各量 1 次，台灣）。映像有預編譯 `.pyc`（`UV_COMPILE_BYTECODE=1`）：沒有它時，每次喚醒都要重新編譯所有套件，約慢 3 秒以上。
- **面試或給人看之前，先自己開一次網址暖機。**
- 想完全沒有冷啟動：`fly.toml` 的 `min_machines_running` 改成 1，代價是常駐計費，約每月 US$3.69。

## 防止 API 額度被濫用

三層（細節見 ADR 0007）：

1. **供應商端上限**（底線）：Anthropic 與 Voyage 都用專用 key，每月上限 US$10。若看到額度用完或服務突然失敗，先去 Anthropic Console 看是否到上限。金鑰外洩就撤銷那把 key。
2. **全站每日 300 次**（`DAILY_ASK_LIMIT`，UTC 日；UTC 零點是台灣早上 8 點重置）。超過時使用者看到「今天的提問額度用完了」。**計數在記憶體，機器重啟（含停機喚醒）就歸零**，所以不是硬上限。
3. **每 IP 每分鐘 10 次**。

要調整額度：`fly secrets set DAILY_ASK_LIMIT=500`（或改 `fly.toml` 的 `[env]`）。

## 看用量與 log

```bash
fly logs                     # 即時 log；每次提問一行 usage（input_tokens／output_tokens，不含問題內容）
fly logs --no-tail | grep usage | tail
```

每次提問約 US$0.012（Sonnet 5.5：輸入 $2、輸出 $10 每百萬 token）。上線後的真實用量以 Anthropic Console 為準。

## 每月更新資料

見 README 的「每月更新資料」。重點：索引是 artifact，重建後要重新 `fly deploy --ha=false` 才會生效；若要更新評估頁，先 `run_generation_eval --publish`。

## 已知小事

- `docker compose up` 要用到 5173 與 8010；本機若已有 `pnpm dev` 在跑 5173，compose 的前端會綁不上去。
- compose 裡的 `data/index` 不能唯讀掛載（Chroma 要寫 SQLite）。
- GitHub Actions 警告：`ubuntu-latest` 會在 **2026-10-19** 起換成 Ubuntu 26，到時 E2E job 的 Playwright 系統套件安裝可能要留意；另外 Node 20 的 action 已被強制改用 Node 24。
- 公開網址上的 `/api/eval/latest` 顯示的是映像裡那一份評估結果，不是即時跑的。
