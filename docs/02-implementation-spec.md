# 交通法規問答系統（Traffic Law RAG）實作規格

> 本文件給 **Claude Code** 使用，以「步驟」為單位，每一步都有目標、工作項目與驗收條件。
> **前置條件**：UI 設計已核准，畫板原始檔與對照表已放在 `docs/design/`（先讀 `docs/design/README.md`）。
> 前端畫面以核准的設計稿為準；互動規則以本文件 5.5 節為準。
> `01-ui-design-brief.md` 是設計前的需求簡報，內容與設計稿或本文件衝突時，以設計稿與本文件為準。

---

## 1. 專案概要

### 1.1 要解決的問題

交通法規條文多、用語艱澀。一般人用白話問問題，但法條使用法律用語，關鍵字搜尋對不上。本系統把白話問題對應到相關條文，**只根據這些條文回答，並且每個論點都標註出處**。

### 1.2 Input / Output

| | 內容 |
|---|---|
| 線上 Input | 一句繁體中文白話問題（上限 200 字） |
| 離線 Input | 全國法規資料庫開放資料中的指定交通法規 |
| Output ① | 串流的白話答案，每個論點附引用標記 |
| Output ② | 被引用條文的原文 |
| Output ③ | 檢索過程：改寫的查詢、檢索結果與分數、各步驟狀態與耗時 |
| Output ④ | 相關條文不足時拒答 |

### 1.3 系統邊界

- 只涵蓋索引內的法規，範圍外的問題要拒答。
- 不提供法律意見；不處理判決、函釋。
- 答案中的數字（罰鍰、記點、期限）必須能在引用條文原文中找到。

---

## 2. 資料來源

### 2.1 取得方式

使用政府資料開放平臺上的全國法規資料庫資料集，皆為每月更新，授權為「政府資料開放授權條款－第 1 版」：

- 中文法規_法律資料檔（data.gov.tw/dataset/18289）
- 中文法規_命令資料檔（data.gov.tw/dataset/18290）

這兩個資料集是全部法規的打包檔，**ingestion 只取目標法規，其餘內容在解析階段即丟棄，不寫入 `data/processed/`、不進索引。**

**不採用的做法：直接爬 `law.moj.gov.tw/LawClass/LawAll.aspx?pcode=...` 頁面。**
該網站的 robots.txt 禁止自動化存取，且 HTML 結構可能隨改版變動。若要以單一法規頁面為來源，只能由人工下載，不得寫爬蟲。此決定寫進 `docs/decisions/0002-data-source.md`。

### 2.2 目標法規

以 **pcode** 作為法規的唯一識別（比法規名稱穩定）：

| 優先級 | 法規 | pcode | 性質 |
|---|---|---|---|
| Must | 道路交通管理處罰條例 | K0040012 | 法律 |
| Must | 道路交通安全規則 | K0040013 | 命令 |
| Must | 道路交通事故處理辦法 | 待 Step 2 確認 | 命令 |
| Should | 強制汽車責任保險法 | 待 Step 2 確認 | 法律 |
| Could | 違反道路交通管理事件統一裁罰基準及處理細則 | 待 Step 2 確認 | 命令；裁罰金額多在附表，能否取得需確認 |

目標清單放在 `backend/app/ingestion/targets.yaml`，新增法規只需改這個檔案並重跑 ingestion。

### 2.3 授權標示

UI footer、關於頁與 README 須註明：法規資料來源為全國法規資料庫（https://law.moj.gov.tw/），由法務部授權使用。文案見設計規格 6.2。

---

## 3. 技術選型

| 層 | 選擇 | 備註 |
|---|---|---|
| 後端 | Python 3.12、FastAPI、Pydantic v2、uv | |
| 向量資料庫 | Chroma（本機持久化） | ADR 說明為何不用 pgvector |
| Embedding | 支援中文的多語言模型，封裝在 `Embedder` 介面後 | 預設 API 型 embedding 以降低部署記憶體；本機模型為替代方案。實作時確認當下最新型號 |
| 關鍵字檢索（Should） | BM25 + jieba 斷詞，與向量檢索以 RRF 合併 | |
| Reranker（Could） | 多語言 cross-encoder | |
| LLM | Claude API，封裝在 `LLMClient` 介面後 | |
| 前端 | React 18 + TypeScript + Vite | |
| 資料請求 | TanStack Query；SSE 用 `fetch` + ReadableStream 解析 | |
| 檢索過程呈現 | PipelineSteps（橫向步驟進度列，核准設計稿的版本） | React Flow 節點圖延後到本專案完成之後，不在範圍內 |
| 樣式 | 依核准設計稿的 token 實作（Tailwind + CSS variables） | token 值見 `docs/design/README.md` |
| 測試 | pytest、Vitest、Playwright | |
| 後端品質 | ruff（lint + format）、mypy strict | |
| 前端品質 | **Biome**（格式 + lint，開啟 recommended 規則與 React hooks 相關規則）、tsc strict | 單一工具取代 Prettier + ESLint |
| CI | GitHub Actions | |
| 部署 | Docker Compose（本機）；Fly.io / Render / Railway 擇一 | |

---

## 4. 系統架構

```
                        ┌──────────────── 離線 ────────────────┐
  開放資料 ZIP ───────▶ │ fetch → filter(pcode) → parse        │
                        │  → chunk → embed → Chroma + BM25     │
                        └──────────────────┬───────────────────┘
                                           │ 索引（含 data_version）
                        ┌──────────────── 線上 ────────────────┐
  React 前端 ──POST──▶  │ FastAPI /api/ask (SSE)               │
     ▲                  │  1. rewrite   改寫為法律用語查詢       │
     │   SSE events     │  2. retrieve  hybrid 檢索 top-k        │
     └────────────────  │  3. rerank    （Could）                │
                        │  4. gate      相關度不足 → 拒答        │
                        │  5. generate  帶引用標記的串流回答     │
                        │  6. validate  驗證引用皆在檢索結果內   │
                        └──────────────────────────────────────┘
```

### 4.1 Repo 結構

```
traffic-law-rag/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── pipeline/       # rewrite, retrieve, rerank, gate, generate, validate
│   │   ├── ingestion/      # fetch, parse, chunk, build_index, targets.yaml
│   │   ├── core/           # config, Embedder, LLMClient
│   │   ├── prompts/        # prompt 檔案
│   │   └── schemas/        # Pydantic models
│   ├── eval/
│   │   ├── dataset.jsonl
│   │   └── run_eval.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── features/ask/
│   │   ├── features/sources/
│   │   ├── features/pipeline/
│   │   ├── features/eval/
│   │   ├── components/         # 共用元件
│   │   ├── styles/tokens.css   # 設計 token
│   │   ├── lib/sse.ts
│   │   └── types/events.ts
│   ├── biome.json
│   └── package.json
├── data/                       # raw/（不進版控）、processed/
├── docs/
│   ├── design/                 # 核准的設計稿：畫板原始檔（*.dc.html）、README（對照表、token）、截圖
│   ├── decisions/              # ADR
│   ├── learning/               # 每步的學習筆記（Step 2–6），見 7.1
│   └── data-format.md
├── docker-compose.yml
├── CLAUDE.md                   # 給 Claude Code 的專案說明與目前進度
└── README.md
```

---

## 5. 資料與介面規格

### 5.1 Chunk Schema

一條條文 = 一個 chunk；條文超過上限（例如 800 字）時依「項」切分並保留所屬條文參照。

```python
class LawChunk(BaseModel):
    chunk_id: str            # "{pcode}:{article_no}" 或 "{pcode}:{article_no}-p{n}"
    pcode: str               # K0040012
    law_name: str            # 道路交通管理處罰條例
    law_short_name: str      # 道交處罰條例（顯示用，定義在 targets.yaml）
    law_level: Literal["法律", "命令"]
    article_no: str          # "53"、"53-1"（條之一）
    paragraph_no: int | None
    chapter: str | None
    text: str                # 條文原文
    embed_text: str          # 法規名稱 + 章節 + 條號 + 原文
    source_url: str          # 該條在全國法規資料庫的連結（給使用者點擊），格式見下
    amended_date: str        # 最新異動日期
    data_version: str        # 資料下載日期
```

`source_url` 格式：`https://law.moj.gov.tw/LawClass/LawSingle.aspx?pcode={pcode}&flno={article_no}`
（例：`...?pcode=K0040012&flno=35-1`）。連結只到「條」；依項切分的 chunk（`-p{n}`）也連到所屬條文，不帶項的參數。這是給使用者點擊的外部連結，系統本身不抓取該頁面。

**條文識別**：UI 以「條」為單位，識別字串為 `{pcode}:{article_no}`（下稱 `article_id`）。未切分的條文 `chunk_id` 等於 `article_id`；切分後的 chunk 去掉 `-p{n}` 即為 `article_id`。

### 5.2 API

| Method | Path | 說明 |
|---|---|---|
| `POST` | `/api/ask` | Body `{ "question": str }`，回傳 SSE |
| `GET` | `/api/chunks/{chunk_id}` | 該 chunk 的欄位，加上 `article_text`（所屬條文的**整條**全文；chunk 依項切分時為各項合併）。全文面板與手機抽屜用 |
| `GET` | `/api/meta` | 收錄法規清單（全名、簡稱、法律／命令、條文數、最新異動日）與 `data_version`。首頁「收錄範圍」、頁首資訊帶、拒答頁用 |
| `GET` | `/api/eval/latest` | 最近一次評估結果 |
| `GET` | `/api/health` | 健康檢查 |

`/api/ask` 需有速率限制與 200 字上限。超過速率限制時回 HTTP 429，並帶 `Retry-After`（秒），前端用它顯示倒數。

### 5.3 SSE 事件

共用外框：`{ "type": string, "run_id": string, "ts": number, "data": object }`。前端以 discriminated union 對應。

| type | data |
|---|---|
| `run.started` | `{ question }` |
| `step.started` | `{ step: "rewrite"\|"retrieve"\|"rerank"\|"gate"\|"generate"\|"validate" }` |
| `step.completed` | `{ step, duration_ms, summary }` |
| `rewrite.result` | `{ queries: string[] }` |
| `retrieval.results` | `{ items: [{ chunk_id, pcode, law_name, law_short_name, article_no, score, snippet, rank, source_url, amended_date }] }` |
| `answer.delta` | `{ text }` |
| `answer.citation` | `{ marker, chunk_id }` |
| `answer.refused` | `{ reason: "low_relevance"\|"out_of_scope", top_score, threshold }` |
| `validate.result` | `{ valid: string[], invalid: string[] }` |
| `run.completed` | `{ total_ms }` |
| `error` | `{ code, message }` |

與畫面的對應：

- 畫面上的步驟固定 5 個：改寫問題（`rewrite`）→ 檢索條文（`retrieve`，有 `rerank` 時併入這一步，不另外顯示）→ 相關度檢查（`gate`）→ 產生答案（`generate`）→ 驗證引用（`validate`）。
- `step.completed.summary` 是給畫面顯示的一行短文字，例如「2 個查詢」「top 5」「最高 0.88 ≥ 門檻」「3 個引用」「3 / 3 通過」。
- 收到 `answer.refused` 時，前端把「相關度檢查」標為相關度不足、後兩步標為略過；後端不需為略過的步驟發事件。
- `retrieval.results` 的欄位足以畫出依據卡片與檢索結果列表（不需再逐筆打 API）；條文全文在開啟面板時才用 `/api/chunks/{chunk_id}` 取得。

### 5.4 引用與拒答

- Prompt 要求以 `[[chunk_id]]` 標記引用，且只能引用 prompt 中提供的 chunk。
- 串流時即時解析標記並發出 `answer.citation`。
- `validate` 檢查引用是否都在本次檢索結果內，不在的列為 invalid。
- 拒答兩層：① 檢索最高分低於門檻直接拒答；② 模型判斷條文不足時輸出固定拒答標記。

### 5.5 前端互動規則（設計 review 結論）

本節記錄設計 review 定案的行為。畫板與元件的對照、token 值見 `docs/design/README.md`；外觀細節（尺寸、間距、各狀態樣式）直接看畫板。

#### A. 版面

- **桌面（≥ 1024px）**：內容最大寬 1240px、左右邊距 32px。問答結果頁為兩欄 7fr／5fr、欄距 40px。
- 左欄順序固定為「你的問題 → 檢索過程 → 答案」，串流中與完成後都不變。
- 右欄是「依據」（ArticleCard 列表）。串流中依檢索分數排序，不因引用出現而重排；完成時排成「已引用在上、未引用在下」，組內依分數。
- 頁首：深色資訊帶（收錄法規、資料更新日）＋產品名稱＋主選單（問答／收錄範圍／評估結果／關於）。「收錄範圍」連到首頁的收錄範圍區塊。
- 頁尾：資料來源與授權標示＋精簡版免責聲明，每頁都有。
- **手機（< 768px）**：見 E。左右邊距 16px，不可出現水平捲動。

#### B. 階段與可互動性

| 階段 | 檢索過程 | 答案 | 依據 |
|---|---|---|---|
| 串流中 | 展開；步驟依 `step.*` 更新；標示「完成後自動收合」 | 逐字出現並帶游標；引用標記以**不可點**的樣式顯示；有「停止」按鈕 | 卡片隨檢索結果出現；沒有連結、沒有 active 外框、不可點 |
| 完成 | 自動收合成一行摘要（例：「✓ 5 個步驟完成 · 檢索到 5 條 · 3.2 秒」），可手動展開 | CitationBadge 可點；下方資訊列顯示引用驗證結果、資料版本、耗時、「重新提問」 | 卡片可點（見 C、D） |
| 已停止 | 停在當下狀態 | 顯示「你已停止產生，答案不完整」與「重新產生」 | 同串流中 |
| 拒答 | 以「為什麼不回答」呈現：PipelineSteps 的拒答分支＋最高相似度與門檻的對照條 | RefusalNotice 取代答案 | 右欄改為「目前收錄的法規」 |
| 錯誤 | — | ErrorNotice（一般錯誤：重試＋回首頁；速率限制：倒數結束前「重試」停用） | — |

串流中任何引用與卡片都不可點擊，是刻意的設計。

#### C. Active 條文（全頁同時只有一條）

- 全頁共用一個狀態 `activeArticleId`（值為 `article_id`），答案、依據、全文面板都讀它。
- **點 CitationBadge**：設為 active。該 badge 變成填滿主色；對應的 ArticleCard 顯示主色外框（底色維持 surface，不使用黃色底）；卡片不在可視範圍時捲入。面板已開啟時，面板內容同步切換。只點 badge 不會開啟面板。
- **點 ArticleCard 的標題或「查看全文」**：設為 active，並開啟全文面板。
- **關閉面板**：active 不變。
- hover 已引用的卡片時，答案中對應的 badge 同步顯示 hover 樣式（反向亦同）。
- 依據以「條」為單位：同一條被切成多個 chunk 且都被檢索到時，只顯示一張卡片（取最高分）；badge 與面板同樣以條為單位。
- 文字格式：badge 為「{簡稱} §{條號}」（例：道交處罰條例 §35-1）；卡片與面板標題為「{簡稱} 第 {條號} 條」。

#### D. 條文全文

- ArticleCard 只放摘要（以行數截斷），不在卡片內展開全文。
- **桌面：頁面下方的全文面板（ArticlePanel）**。不是 modal：沒有遮罩、不鎖住頁面。版面是「可捲動的頁面區」與「固定高度的面板」上下排列，不是覆蓋，因此面板開啟時，答案與依據仍可捲動並看到完整內容。
- 面板內容：深色標題列（「條文全文」、簡稱＋條號、「在全國法規資料庫查看 ↗」、右上角關閉按鈕）；內文左欄為引用狀態、法規全名、「第 N 條」、最新異動日；右欄為可捲動的條文全文。切換條文時，內文捲回頂端。
- **手機：底部抽屜**（dialog，有遮罩）。內容為完整條文、最新異動日、外部連結；底部「← 上一則」「下一則 →」在本次檢索到的條文間切換，到頭尾時停用。
- 全文一律顯示**整條**條文（取自 `/api/chunks/{chunk_id}` 的 `article_text`），各項的樣式一致，不特別標示被引用的項。
- 「在全國法規資料庫查看 ↗」使用 `source_url`，另開新視窗，`aria-label` 帶法規與條號。

#### E. 手機（< 768px）

- 問答結果頁有兩個分頁：「答案」｜「過程與依據」。
- 「答案」：問題、答案（含 badge）、引用驗證結果、資料版本與耗時、整行寬的「重新提問」、精簡版免責聲明。
- 「過程與依據」：上方是檢索過程（**預設展開**，直式步驟列表，可收合）；下方是依據列表（已引用：分數、分數條、兩行摘要；未引用：虛線框，只有標題與分數條）。
- 點答案中的 badge，或點依據列表的項目，都開啟條文抽屜。
- 首頁：多行輸入框、整行寬的「提問」按鈕、4 個範例問題。

#### F. 無障礙與狀態

- 狀態不能只靠顏色：badge 的驗證失敗用虛線框＋圖示，步驟狀態有符號（✓／進行中／○／—／⨯），卡片 hover 有底線或線型變化。
- 鍵盤 focus 樣式為 3px 深色外框、間距 2px，與 hover 樣式分開。
- 可點元件最小高度 44px（行內的 CitationBadge 為 28px）。
- 元件需要的狀態以 `Components.dc.html`、`States.dc.html` 兩張畫板為準。

#### G. 設計稿沒有涵蓋、先採用的預設

以下在設計稿中沒有對應畫面。先照這些預設實作，想改時先提出：

1. 回答完成時，預設 active 為答案中的第一個引用（與「回答完成」畫板的初始狀態一致）；全文面板預設關閉。
2. 平板（768–1023px）：單欄，依據移到答案下方；全文沿用下方面板。
3. 手機串流中：停留在「答案」分頁，檢索過程在「過程與依據」分頁更新。
4. 暗色模式預設跟隨系統設定（`prefers-color-scheme`）。（2026-10-07 依 Leanne 的意見修訂，原本是「不做切換按鈕」。）
   - 頁首有一個外觀切換按鈕，輪流切換「跟隨系統 → 亮色 → 暗色」，位置在主選單那一列的最右邊（首頁刊頭在 GitHub 按鈕下方；精簡頁首在同一列最右；手機放在選單最後一項）。
   - 選擇存在瀏覽器（`localStorage`，讀寫失敗就跟隨系統），以 `<html data-theme="light|dark">` 套用；跟隨系統時沒有這個屬性。`index.html` 在繪製前先套用，避免先閃一下系統預設的顏色。
   - 設計稿沒有這個按鈕，樣式沿用主選單的文字樣式（圖示＋目前外觀的名稱）。
5. Esc 可關閉全文面板與抽屜；關閉後焦點回到開啟它的元素。
6. 拒答頁「可以試著這樣問」：從首頁範例問題取 2 題，加上「換個問題」。由 LLM 產生改問建議列為 Could。
7. 手機選單內容與桌面主選單相同。
8. 問題放在網址：`/` 是首頁，`/?q=<問題>` 是這一題的結果頁（2026-10-07 依 Leanne 的意見修訂，原本是「問答狀態只存在記憶體，重新整理後回到首頁」）。
   - 提問時網址變成 `/?q=…`，並新增一筆瀏覽紀錄，所以上一頁可以回到首頁或上一個問題。
   - 網址是唯一的來源：開啟 `/?q=…`（重新整理、分享連結、上一頁／下一頁）會**重新提問**，會再花一次模型費用並計入速率限制。回答結果本身仍不保存。
   - 重試、重新產生（同一題）不改網址；「重新提問」「換個問題」「回首頁」回到 `/`。
   - 切到其他頁面（關於、評估結果）再回來時，進行中或已完成的問答保持原樣，不重新提問。
   - 頁面標題在結果頁是「{問題}｜交通法規資料庫」。

#### H. 已確認的設計決定

- **產品名稱**：「交通法規資料庫」。頁首刊頭、頁面標題、手機標題列一律使用這個名稱。專案與 repo 名稱仍是 Traffic Law RAG，兩者不必相同。
- **陰影**：不使用陰影的原則維持不變，唯一的例外是桌面全文面板的上緣陰影（`--shadow`），是刻意保留的，用來表現面板與頁面不同層。不要把陰影用到其他元件。
- **React Flow 節點圖**：延後到本專案完成之後，不在範圍內（見優先級）。

---

## 6. 實作步驟

### 優先級

- **Must**：Step 1–8、Step 9（PipelineSteps 版）、Step 10、Step 11（E2E 除外）、Step 12、Step 13
- **Should**：hybrid 檢索、Step 11 的 Playwright E2E
- **Could**：reranker、裁罰基準附表、拒答頁由 LLM 產生改問建議
- **延後（不在本專案範圍）**：React Flow 節點圖。核准的設計是 PipelineSteps；README 的「後續方向」可提到它

時間不夠時依序砍：reranker → 裁罰基準附表 → hybrid 檢索。

---

### Step 1：專案骨架

- 依 4.1 建立 monorepo；backend 用 uv，frontend 用 Vite React TS
- FastAPI `/api/health`；前端顯示 health 狀態
- `docker-compose.yml` 一鍵啟動
- 後端：ruff（lint + format）、mypy strict、pytest
- 前端：Biome（`biome check`：格式 + lint）、tsc strict、Vitest
- GitHub Actions：`biome ci`、ruff、mypy、tsc、test
- `.env.example`；config 用 pydantic-settings
- ADR `0001-tech-stack.md`

**驗收**：`docker compose up` 可看到前端連上後端；CI 綠燈。

---

### Step 2：資料取得與格式確認

- `ingestion/fetch.py`：下載法律、命令兩個資料集 ZIP 到 `data/raw/{date}/`；同一份資料只下載一次（有快取就跳過）
- 依 `targets.yaml` 的 pcode 過濾，只解出目標法規
- 查出 2.2 表中「待確認」的 pcode，寫回 `targets.yaml`
- 實際檢查資料格式，寫成 `docs/data-format.md`（附一條條文的原始範例）
- 確認：項、款是否已分開；「條之一」表示方式；附件是內容還是只有檔名；廢止註記
- `ingestion/parse.py`：轉成中介 JSON，排除已廢止法規
- ADR `0002-data-source.md`（為何用開放資料打包檔、不爬網頁）

**驗收**
- `data/processed/` 只有目標法規
- `docs/data-format.md` 明確記錄裁罰基準附表能否取得
- 各法規條文數與全國法規資料庫網站一致（人工抽查）
- parse 有 pytest，fixture 用真實片段

---

### Step 3：Chunking 與建索引

- `ingestion/chunk.py`：依 5.1 產生 `LawChunk`
- `ingestion/build_index.py`：寫入 Chroma；（Should）建 BM25 索引
- 索引記錄 `data_version`，`/api/meta` 讀出
- 輸出統計：各法規 chunk 數、平均／最大長度
- ADR `0003-chunking.md`

**驗收**：重跑結果一致；無空白或重複 chunk。

---

### Step 4：檢索與評估集 v0

在接 LLM 之前先證明檢索品質。

- `pipeline/retrieve.py`：向量檢索（＋ hybrid 時 RRF 合併）
- CLI：`uv run python -m app.pipeline.retrieve "紅燈右轉罰多少"` 印出 top-k 與分數
- `eval/dataset.jsonl`，25～30 題：

```json
{"id": "q01", "question": "紅燈右轉會被罰多少錢？", "category": "fine_amount",
 "expected_chunk_ids": ["K0040012:53"], "expected_facts": ["..."],
 "should_refuse": false, "verified": false}
```

- 類別：罰鍰金額、行為定義、事故處理、跨法規、口語問法、範圍外（至少 4 題應拒答）
- Claude Code 可產生題目草稿，但 `expected_chunk_ids`、`expected_facts` 一律 `verified: false`，由 human 人工對照條文確認
- `eval/run_eval.py`：Recall@5、MRR；只計入 `verified: true` 的題目

**驗收**：一行指令跑出評估 JSON；記錄 baseline；有 hybrid 時比較兩者並寫 ADR。

---

### Step 5：生成、引用與拒答（非串流）

- `pipeline/rewrite.py`：口語問題改寫為 1～3 個法律用語查詢
- `pipeline/gate.py`：相關度門檻
- `pipeline/generate.py`：只根據提供的條文、必須用 `[[chunk_id]]` 引用、數字照抄條文、不足時輸出拒答標記
- `pipeline/validate.py`
- prompt 放 `app/prompts/` 進版控
- `run_eval.py` 加上：引用正確率、數字正確率、拒答正確率

**驗收**：五項指標都能輸出；範圍外題目會拒答；invalid 引用全部被抓到。

---

### Step 6：SSE 串流 API

- `/api/ask` 依 5.3 發送事件；每一步都 emit `step.started` / `step.completed`
- 串流中即時解析引用
- LLM 逾時、API 失敗轉為 `error` 事件，stream 正常結束
- 速率限制（HTTP 429 ＋ `Retry-After`）、長度上限
- `/api/chunks/{id}`（含 `article_text` 整條全文）、`/api/meta`（收錄法規清單）
- 拒答時 `answer.refused` 帶 `top_score` 與 `threshold`

**驗收**：`curl -N` 可看到完整事件序列（一般回答與拒答各一次）；pytest 用假的 LLMClient 驗證事件順序與 schema；依項切分的 chunk 取回的 `article_text` 是整條條文。

---

### Step 7：前端──版面骨架、提問與串流答案

畫板：`Tokens`、`Main`、`MobileHome`、`Streaming`、`Refusal`、`States`、`About`；`Components` 的 QuestionInput、ExampleQuestions、Button、DataVersionBadge、Disclaimer 區塊。

- 把設計 token 落地成 `styles/tokens.css`（亮色＋暗色，值見 `docs/design/README.md`）；元件只用變數，不寫死色碼。字型：Noto Serif TC、Noto Sans TC、IBM Plex Mono
- 共用版面：頁首（資訊帶、產品名稱、主選單）、頁尾（資料來源標示、精簡版免責聲明）；路由 `/`、`/eval`、`/about`
- `lib/sse.ts`、`types/events.ts`；問答狀態機：`idle → streaming → done | refused | stopped | error`
- 首頁：QuestionInput（字數計數、超過 200 字的錯誤狀態）、ExampleQuestions（桌面 6 題、手機 4 題）、收錄範圍（資料來自 `/api/meta`）、完整版免責聲明
- 問答結果頁骨架：依 5.5-A 的固定順序排好三個區塊；AnswerStream（游標、已停止狀態）；串流中的引用標記先以不可點的樣式顯示（互動留到 Step 8）；「停止」與「正在產生答案…」；「重新提問」
- 檢索過程區塊此步只需能顯示目前進行到哪一步的文字，完整的 PipelineSteps 與 RetrievalPanel 在 Step 9
- RefusalNotice 與右欄「目前收錄的法規」（「為什麼不回答」區塊留到 Step 9）；ErrorNotice（一般錯誤、速率限制倒數）
- 關於頁（靜態內容，照 `About` 畫板）

**驗收**
- 與設計稿並排截圖比對（桌面 1440px、手機 390px、暗色各至少一張），附在 PR 描述
- 串流中斷時有明確錯誤提示；按「停止」後顯示已停止狀態
- 串流中答案與依據沒有任何可點擊的元素
- Vitest 覆蓋 SSE 解析器與問答狀態機

---

### Step 8：前端──引用、依據與條文全文

畫板：`Answer`、`AnswerDark`、`ArticlePanel`、`MobileAnswer`、`MobileAnswerDark`、`MobileProcess`（依據列表部分）、`MobileSources`；`Components` 的 CitationBadge、ArticleCard 區塊；`States` 的引用驗證警告。規則見 5.5 的 B、C、D、E。

- CitationBadge：預設／hover／active／focus／驗證失敗
- ArticleCard：已引用／未被引用／選中，以及各自的 hover 與 focus；卡片只放摘要；與 badge 的雙向 hover
- 依據以「條」為單位合併 chunk；完成時的排序
- `activeArticleId`：全頁唯一，badge、卡片、面板共用
- ArticlePanel（桌面下方全文面板）：開啟、切換條文、關閉；開啟時頁面區仍可捲動
- 引用驗證：答案下方的驗證結果、驗證失敗的 badge 樣式與說明、答案上方的提示列
- 手機：兩個分頁、依據列表、條文抽屜（上一則／下一則）

**驗收**
- 每個引用都能對到正確條文；任何時候最多只有一條 active
- 面板開啟時，答案與依據可捲到最底；點另一個 badge 或卡片，面板內容與卡片外框一起切換
- 依項切分的條文，面板顯示的是整條全文
- 全程可用鍵盤操作；Esc 關閉面板與抽屜
- 與設計稿並排截圖比對（`Answer`、`ArticlePanel`、`MobileSources`），附在 PR 描述

---

### Step 9：前端──檢索過程

畫板：`Streaming`、`Answer`（展開檢索過程時）、`Refusal`、`MobileProcess`；`Components` 的 PipelineSteps、RetrievalPanel 區塊。規則見 5.5 的 B、E。

- PipelineSteps：5 個步驟，狀態為等待／進行中／完成／略過／相關度不足；每步顯示摘要文字與耗時；依 `step.*` 事件更新
- RetrievalPanel：改寫後的查詢、排名、法規與條號、分數條與分數；完成後標示已引用／未引用；載入中（骨架）與無結果狀態
- 桌面：串流中展開，完成時自動收合成一行摘要，可手動展開／收合
- 手機：放在「過程與依據」分頁上方，預設展開，直式列表
- 拒答頁的「為什麼不回答」：PipelineSteps 的拒答分支＋最高相似度與門檻的對照條（用 `answer.refused` 的 `top_score`、`threshold`）
- 不做 React Flow 節點圖（延後到本專案完成之後）；Step 9 只做 PipelineSteps

**驗收**：一次提問中各步驟的狀態轉換正確；拒答時後兩步顯示為略過；完成時自動收合；Vitest 覆蓋「事件序列 → 步驟狀態」的轉換。

---

### Step 10：評估頁

畫板：`Eval`；`Components` 的 MetricCard 區塊。

- `run_eval.py` 輸出 JSON，`/api/eval/latest` 提供
- MetricCard × 5（指標名稱、英文代號、數值、一句白話說明）
- EvalTable：欄位為編號、問題、類別、檢索、引用、數字；每列可展開看標準答案與系統檢索前 5 筆；可依類別篩選；附符號說明
- 顯示評估日期、資料版本、題數（含範圍外題數）

**驗收**：頁面數字與 CLI 一致；畫板上的 `[XX]`、`[N]` 等佔位符全部換成實際資料，沒有殘留。

---

### Step 11：測試與品質收尾

- 後端：pipeline 單元測試、API 整合測試（假 LLM）
- 前端：關鍵元件測試；（Should）Playwright E2E：點範例問題 → 看到答案與引用
- CI 加 E2E（可只在 main 跑）

**驗收**：CI 綠燈；README 有 CI badge。

---

### Step 12：部署

- 後端 Dockerfile；索引在 build 時產生或作為 artifact 掛載（寫 ADR）
- 前端靜態部署；環境變數、CORS、速率限制
- README 說明每月手動重跑 ingestion 更新資料

**驗收**：公開 URL 可用；冷啟動時間與月成本估算寫進 README。

---

### Step 13：README 與 demo 素材

README 結構：

1. 一句話介紹、30 秒 demo GIF、線上連結
2. 要解決的問題與 Input / Output
3. 架構圖
4. 評估結果與方法
5. 技術取捨（連到 ADR）：資料來源、chunk 策略、Chroma vs pgvector、hybrid 檢索、引用驗證、拒答設計。素材取自 `docs/learning/` 與 ADR，由 Claude Code 起草、human 逐段改寫
6. 遇到的困難與解法
7. 限制與後續方向
8. 資料來源與授權標示、免責聲明

**驗收**：沒看過專案的人三分鐘內能理解系統做什麼、好在哪。

---

## 7. 執行規則

- 依步驟順序執行；每步完成時逐項對照驗收條件並回報。是否停下來等 review，依 7.1 的 review 強度與檢查點決定。
- 實際情況與本文件不符時（例如資料格式不同），先更新 `docs/data-format.md` 或相關 ADR 並回報，不自行假設後繼續。
- 重要技術決策寫 ADR（背景、選項、決定、後果）。
- 不寫爬蟲存取 `law.moj.gov.tw` 的網頁。
- API key 不進程式與版控；`data/raw/` 不進版控。
- 評估集標準答案只能由人工確認。
- 前端以核准設計稿為準；需偏離時先提出，不自行改版面。
- 畫板是參考，不是程式碼：取其結構、尺寸與 token，用 React 元件重寫；不要搬畫板的模板語法（`{{ }}`、`<sc-if>`、`<sc-for>`、`DCLogic`）或整段 inline style。
- 畫板裡的內容是示意資料（條文文字、`[金額]`、相似度分數、日期、`[XX]`），一律不得寫進程式或測試當作真實資料；畫面上的資料全部來自 API。
- 畫板之間不一致時，依 `docs/design/README.md` 的「以誰為準」處理；那裡也沒寫的，先問。
- 5.5-H 是已確認的設計決定，直接照做。

### 7.1 Review 強度與學習流程

依熟悉度分三種做法，並以指標、測試與獨立 review 取代逐行檢視後端程式碼。

**A. 各 Step 的做法**

| Step | 做法 |
|---|---|
| 1、7–12（骨架、前端、評估頁、測試、部署） | 一口氣做：簡短說明做法後直接實作，不等核准；完成後對照驗收並回報 |
| 2、3（資料、chunking） | 先提計畫並等確認；重點是資料長什麼樣、怎麼切，用統計輸出與 `docs/data-format.md` 呈現，不要求讀程式碼 |
| 4、5、6（檢索、生成、SSE） | 學習流程（見 B） |
| 13（README） | Claude Code 起草，human 逐段改寫成自己的話 |

**必停的檢查點**：Step 3、4、5、6、9 完成後停下來，等 human 檢視。檢查的內容：

- Step 3 後：資料與索引。看 `docs/data-format.md`、各法規 chunk 統計、抽樣幾條 chunk 的實際內容。
- Step 4 後：檢索 baseline。看評估結果與 human 自己跑的實驗。
- Step 5 後：生成、引用與拒答。看五項評估指標；用幾個真實問題讀完整答案，確認引用對得上條文、數字照抄條文；範圍外問題確實拒答；故意製造無效引用，確認會被標成 invalid。
- Step 6 後：API 跑通。用 `curl -N` 看事件序列（一般回答、拒答各一次）。
- Step 9 後：前端完成。照 Step 7–9 的驗收，並排比對設計稿截圖。

其餘 Step 驗收通過後可接著做下一個 Step，但每步仍各自 commit、各自對照驗收、更新 `CLAUDE.md` 的進度。

**B. 學習流程（Step 4、5、6）**

1. **開工前**：先用前端工程師熟悉的類比，解釋這一步的核心概念與最常見的坑（例如 embedding 與相似度分數、RRF、拒答門檻為什麼存在、SSE 與一般 API 的差別），不要留下未解釋的術語。再提實作計畫，等 human 確認。
2. **實作中**：照 spec 做，不需要 human 盯著。
3. **完成後**：不要求讀 diff。改給一份「請 human 自己跑的實驗清單」，每項附上指令與預期要觀察什麼。例如 Step 4：
   - 用 CLI 問 10 個問題，看排名與分數；
   - 故意問範圍外的問題，看最高分落在哪，由此理解門檻怎麼訂；
   - 改 top-k 或 chunk 大小，重跑評估，看數字怎麼變。
4. **收尾**：寫 `docs/learning/step-N.md`（見 C）。

**C. 學習筆記（Step 2–6）**

- 檔名 `docs/learning/step-N.md`，一頁內，白話。
- 內容只有四塊：這步做了什麼；為什麼選這個方法而不是另一個（放棄了什麼）；什麼情況下會壞掉；面試可能被問的 3 個問題與簡短回答。
- Claude Code 寫的是草稿，檔案開頭標 `狀態：草稿`。human 用自己的話改寫後改成 `狀態：已改寫`。Step 13 的 README 技術取捨以已改寫的筆記為素材。

**D. 後端品質怎麼把關**

- 後端不靠逐行 review。靠 pytest、評估指標（Recall@5、MRR、引用／數字／拒答正確率），以及獨立 review。
- 改動 chunking、檢索參數、門檻或 prompt 之後，必須重跑評估，並在回報中列出前後數字。數字變差要說明原因，不得只回報「已完成」。
- 檢查點之前，建議 另開一個全新 session（或 subagent），只給它 spec 與該階段的 diff，請它找 bug、和 spec 不符之處、沒被測到的地方，並用白話說明結論。可用這段 prompt：

  ```
  你是獨立的 reviewer，沒有參與實作。只根據 docs/02-implementation-spec.md 和這個階段的 diff，
  找出：1) bug 與邊界情況 2) 與 spec 不符之處 3) 沒被測試涵蓋的行為 4) 資料或評估上可能讓指標失真的地方。
  用白話說明，每項標示嚴重程度，不要修改任何檔案。
  ```
