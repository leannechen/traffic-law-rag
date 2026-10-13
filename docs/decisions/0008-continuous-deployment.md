# ADR 0008：持續部署（CD）

狀態：已採用（Step 12 之後的補充）。ADR 0007 當時決定手動部署；這份補上 push 後自動部署。

## 背景

部署一直是本機 `fly deploy --ha=false`。問題是容易忘記部署、部署前沒有檢查 CI 是否通過，而且靠人記得 `--ha=false`。

卡點是**索引不進 git**（`data/index/`，約 6 MB，由 Voyage 嵌入產生，ADR 0007），映像卻是 `COPY data/index` 建起來的。GitHub 的 runner 拿不到索引，所以 CD 必須先決定索引從哪裡來。

## 選項

| 方案 | 做法 | 為什麼沒選（或選了） |
|---|---|---|
| A. CD 裡重建索引 | runner 先 fetch → parse → build_index 再部署 | 每次 push 都要下載約 100 MB 資料包、呼叫 Voyage；且同一份資料重算的向量不保證逐位元相同，部署的索引會悄悄變動 |
| **B. 索引放 GitHub Release** | 每個資料版本一個 Release（tag `data-YYYY-MM-DD`，asset `index.tar.gz`）；CD 下載最新一份 | **採用。** push 程式碼的 CD 很快、結果可重現，索引有明確版本 |
| C. 索引 commit 進 git | 直接 commit 6 MB | 每月多一份二進位 diff，repo 只會越來越大；ADR 0007 當初就決定不進版控 |

## 決定

在 `ci.yml` 新增 `deploy` job：

1. **條件**：push 到 main（或手動觸發），而且 `backend`、`frontend`、`e2e`、`image` 四個 job 都成功。PR 與 fork 不會觸發，也拿不到 secret。
2. **全自動**：不設人工核准關卡。風險由 CI、映像 smoke test 與部署後的 smoke test 擋。
3. **跳過只改文件的 push**：比對 `github.event.before..sha` 的改動檔案，只動 `docs/`、`.github/`、`frontend/scripts/`、`frontend/e2e/`、`backend/tests/`、README、`CLAUDE.md` 時不部署。原因：部署會重啟機器，記憶體裡的每分鐘速率限制與每日 300 次額度會歸零，頻繁重啟會削弱防濫用（ADR 0007）。手動觸發（`workflow_dispatch`）一律部署。
4. **索引**：`gh release list` 取 tag 以 `data-` 開頭、字典序最大（日期最新）的一個，下載 `index.tar.gz` 解到 `data/`，檢查 `index_meta.json` 存在。
5. **部署**：`flyctl deploy --remote-only --ha=false`，用 Fly 的遠端 builder 建映像。`concurrency` 群組讓兩次 push 的部署排隊，不互相覆蓋。
6. **部署後 smoke test**：`/api/health`，並把 `/api/meta` 的 `data_version`、`embedding_model`、`chunk_count` 與下載的 `index_meta.json` 比對；不符就讓 job 失敗。最後確認首頁回的是前端，並印出 `flyctl status`。
7. **權限最小化**：job 只有 `contents: read`；唯一的 secret 是 `FLY_API_TOKEN`，用 `fly tokens create deploy -a traffic-law-rag` 產生，只能部署這一個 app。
8. **action 以 commit SHA 釘版**（`setup-flyctl`），不用會移動的 tag 或 `master`。

## 放棄了什麼

- **人工核准關卡**：CI 綠燈後還要按一下才部署。作品集流量低、改動由我自己控制，不值得多一道手續。
- **每月資料更新的自動化**：這份只處理「程式碼 push 後部署」。資料更新仍是手動：重建索引、上傳成新 Release、再手動觸發部署（見 `docs/operations.md`）。
- **自動回滾與備援機器**：只有一台機器，部署是原地替換；新版 health check 沒過時，Fly 不一定能留著舊版（我沒有實測過單機失敗的行為）。所以失敗時要手動回復：`fly releases` 找上一版、`fly deploy --image <上一版映像> --ha=false`。health check 沒覆蓋的問題（例如回答品質）也不會被擋下，要靠人看。第一次用 CD 時，我會在你有空盯著時驗證，不在離開時才部署。
- **預覽環境**：只有一個 app、一個環境。

## 驗證結果（2026-10-12）

| 路徑 | 結果 |
|---|---|
| 只改文件的 push | 跳過部署，CI 成功 |
| 手動觸發（`workflow_dispatch`） | 部署成功（Fly v3 → v4） |
| 改到程式碼的 push | 自動部署成功（v5）；smoke test 的 `data_version`、`embedding_model`、`chunk_count` 與索引一致；仍是單機、health check 通過 |

**未實測**：部署失敗時單機的行為、找不到 `data-*` Release 時的失敗路徑、force push 與新分支（程式裡寫成一律部署）。

## 後果

- 手動 `fly deploy --ha=false` 仍可用，作為備援與每月更新資料時使用；兩者共用同一個 Fly app，`concurrency` 只管 CI 這一側。
- 部署中那台機器會重啟，使用者可能遇到數秒到十幾秒的中斷；作品集流量低，可以接受。
- **索引與程式碼的版本必須匹配**：若改了 chunk 結構或 embedding 模型，CD 會抓到舊索引。部署後 smoke test 比對 `embedding_model` 與 `chunk_count` 只能攔住部分情況；改結構時，要**先建好新索引並發新 Release，再 push 程式碼**。
- **第一次使用前**要有一個 `data-*` Release，否則 `deploy` job 會失敗並中止（線上不受影響）。
- 部署會重啟機器，記憶體內的額度歸零（所以才要跳過只改文件的 push）。
- 內建的 `GITHUB_TOKEN` 只用來讀 Release；repo 是私有的，Release asset 只有協作者能下載。
- 第三方 action 的信任：`setup-flyctl` 由 Fly 官方維護，釘在 commit SHA；要升級時手動換 SHA。
