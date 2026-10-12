# 維運筆記

線上版：https://traffic-law-rag.fly.dev/（Fly.io，單機，region `nrt`）。決策背景見 [ADR 0007](decisions/0007-deployment.md)。

## 部署

**平常是自動的**（ADR 0008）：push 到 main，CI 的四個 job 都過了之後，`deploy` job 會下載最新的資料 Release、`flyctl deploy --remote-only --ha=false`，再對公開網址做 smoke test。只改文件、CI 設定、測試時會跳過（部署會重啟機器，額度歸零）。

- 需要 GitHub secret `FLY_API_TOKEN`（`fly tokens create deploy -a traffic-law-rag`，Settings → Secrets and variables → Actions）。token 外洩或輪替時，先撤銷（`fly tokens list`、`fly tokens revoke`）再重建並更新 secret。
- 不想等 push、或跳過了但想部署：Actions 頁面 → CI → Run workflow（選 main）；手動觸發一律部署。
- `deploy` job 失敗：先看 job 的 log；常見原因是找不到 `data-*` Release（這種情況還沒部署，線上不受影響）、token 失效、smoke test 的 `data_version` 與 Release 不符。若是部署到一半失敗、線上壞了：單機沒有備援，用 `fly releases` 找上一版，`fly deploy --image <上一版映像> --ha=false` 回復。
- 改了 chunk 結構或 embedding 模型時，**先建新索引並發新 Release，再 push 程式碼**，否則 CD 會把舊索引配上新程式碼。

### 發佈索引 Release（首次與每月更新）

在 repo 根目錄、`data/index/` 是你要發佈的那份：

```bash
tar -czf /tmp/index.tar.gz -C data index
ver=$(jq -r .data_version data/index/index_meta.json)
gh release create "data-$ver" /tmp/index.tar.gz --title "Index $ver" --notes "data_version $ver"
```

之後 CD 會自動用 tag 日期最新的 `data-*` Release。

### 手動部署（備援）

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

見 README 的「每月更新資料」。重點：索引是 artifact，重建後要**發佈成新的 `data-*` Release**（見上方「發佈索引 Release」），再到 Actions 手動觸發部署（或本機 `fly deploy --ha=false`）才會生效；若要更新評估頁，先 `run_generation_eval --publish`（`latest.json` 要 commit 並 push，CD 會把它帶進映像）。

## 已知小事

- `docker compose up` 要用到 5173 與 8010；本機若已有 `pnpm dev` 在跑 5173，compose 的前端會綁不上去。
- compose 裡的 `data/index` 不能唯讀掛載（Chroma 要寫 SQLite）。
- GitHub Actions 警告：`ubuntu-latest` 會在 **2026-10-19** 起換成 Ubuntu 26，到時 E2E job 的 Playwright 系統套件安裝可能要留意；另外 Node 20 的 action 已被強制改用 Node 24。
- 公開網址上的 `/api/eval/latest` 顯示的是映像裡那一份評估結果，不是即時跑的。
