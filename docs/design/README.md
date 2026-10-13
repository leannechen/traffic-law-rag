# 設計稿（核准版）

這個資料夾是「交通法規問答」UI 設計稿的原始檔，供實作前端時對照。
互動規則寫在 `docs/archive/implementation-spec.md` 的 5.5 節，這裡不重複，只放：畫板對照表、設計 token、畫板之間不一致時以誰為準。

- 匯出日期：2026-10-05
- 截圖：請把從設計稿匯出的畫面圖檔放在 `screenshots/`，檔名與畫板相同（例如 `Answer.png`），做並排比對時使用。

---

## 1. 怎麼讀 `.dc.html`

每個 `.dc.html` 是一張畫板。它依賴 Claude Design 的執行環境（`support.js`），**不能直接用瀏覽器開**，請當成有結構的參考文件來讀：

| 位置 | 內容 |
|---|---|
| `<helmet>` 裡的 `<style>` | `.th-light`、`.th-dark` 兩組 CSS 變數（即設計 token） |
| `<x-dc>` 裡的 HTML | 畫面結構；樣式全部是 inline style，數值可直接對照 |
| `{{ 名稱 }}` | 動態值，定義在檔案最下方 `<script>` 的 `renderVals()` |
| `<sc-if>`、`<sc-for>` | 條件顯示與迴圈 |
| 最下方 `<script>` 的 `state`、`setState` | 可互動畫板的狀態與點擊行為（例如 `active`、`open`） |
| `data-props` 的 `$preview` | 畫板尺寸 |

實作時取其**結構、尺寸、間距與 token**，用 React 元件重寫。不要把模板語法或整段 inline style 搬進程式。

畫板內的文字多數是**示意資料**：條文內容、`[金額]`、`[期間]`、`[YYYY-MM-DD]`、`[XX]%`、相似度分數、耗時、資料更新日都不是真實資料，不可寫進程式或測試。`ArticlePanel.dc.html` 裡第 35 條、第 35-1 條的長條文取自非官方的轉載來源，只用來檢查長文排版，同樣不可當作資料使用。

---

## 2. 畫板對照表

### 桌面（畫板寬 1440px）

| 檔案 | 畫面 | 路由／狀態 | Step | 主要元件 |
|---|---|---|---|---|
| `Main.dc.html` | 首頁（空狀態） | `/`，`idle` | 7 | 首頁刊頭、QuestionInput、ExampleQuestions（6 題）、收錄範圍、Disclaimer 完整版 |
| `Streaming.dc.html` | 串流中 | `/`，`streaming` | 7、9 | 「停止」、AnswerStream（游標、不可點的引用標記）、PipelineSteps（進行中）、RetrievalPanel（載入中）、不可點的依據卡片 |
| `Answer.dc.html` | 回答完成（可互動） | `/`，`done` | 8、9 | CitationBadge、ArticleCard、收合的檢索過程（可展開）、答案資訊列、「重新提問」 |
| `AnswerDark.dc.html` | 回答完成（暗色） | 同上 | 8 | 與 `Answer` 內容相同，預設暗色，用來對照暗色配色 |
| `ArticlePanel.dc.html` | 查看全文：下方面板（可互動） | `/`，`done`＋面板開啟 | 8 | ArticlePanel；畫板高 900px，模擬一個視窗高度內「頁面區＋面板」的分配 |
| `Refusal.dc.html` | 拒答 | `/`，`refused` | 7、9 | RefusalNotice、改問建議、「為什麼不回答」（PipelineSteps 拒答分支＋門檻對照條）、右欄收錄法規 |
| `States.dc.html` | 錯誤、限制、驗證警告 | `/`，`error`／`stopped` 等 | 7、8 | ErrorNotice（一般、速率限制）、QuestionInput 超過字數、AnswerStream 已停止、引用驗證警告與說明 |
| `Eval.dc.html` | 評估結果 | `/eval` | 10 | MetricCard × 5、類別篩選、EvalTable（可展開列） |
| `About.dc.html` | 關於 | `/about` | 7 | 做與不做的事、運作方式 5 步驟（含圖示）、資料來源與授權、Disclaimer 完整版 |
| `Components.dc.html` | 元件與狀態 | — | 7–10 | CitationBadge、次要按鈕、ArticleCard（含 hover／focus）、PipelineSteps、QuestionInput、ExampleQuestions、DataVersionBadge、RetrievalPanel、MetricCard |
| `Tokens.dc.html` | 設計 token | — | 7 | 顏色、字體、間距、線條規則 |

### 手機（畫板 390 × 844px）

| 檔案 | 畫面 | 路由／狀態 | Step | 主要元件 |
|---|---|---|---|---|
| `MobileHome.dc.html` | 首頁 | `/`，`idle` | 7 | 多行輸入框、整行「提問」、ExampleQuestions（4 題） |
| `MobileAnswer.dc.html` | 答案分頁 | `/`，`done` | 8 | 分頁列（答案｜過程與依據）、答案、驗證結果、整行「重新提問」 |
| `MobileAnswerDark.dc.html` | 答案分頁（暗色） | 同上 | 8 | 暗色配色；同時示範**引用驗證失敗**的 badge 與提示文字 |
| `MobileProcess.dc.html` | 過程與依據分頁（可互動） | 同上 | 8、9 | 檢索過程（預設展開、直式）、依據列表（已引用／未引用） |
| `MobileSources.dc.html` | 條文抽屜 | `done`＋抽屜開啟 | 8 | 底部抽屜、整條條文、「上一則／下一則」 |

### 頁首有兩種

- **首頁（`idle`）**：置中的大刊頭、GitHub 連結、主選單在刊頭下方（`Main.dc.html`）。
- **其他頁面與狀態**：精簡頁首，產品名稱與主選單同一列（`Answer.dc.html` 等）。

---

## 3. 設計 token

實作成 `frontend/src/styles/tokens.css`。元件只用變數，不寫死色碼。

### 顏色

| 變數 | 亮色 | 暗色 | 用途 |
|---|---|---|---|
| `--paper` | `#F6EEE3` | `#151311` | 頁面底色 |
| `--surface` | `#FCF7F0` | `#1F1B18` | 卡片、輸入框、全文面板底色 |
| `--sunken` | `#EEE2D2` | `#2A2420` | 凹陷區塊、分數條底、骨架 |
| `--ink` | `#1C1917` | `#F3EBE1` | 主要文字 |
| `--ink2` | `#4F4842` | `#CFC4B8` | 次要文字 |
| `--ink3` | `#645B53` | `#A99D91` | 輔助文字、等待中的狀態 |
| `--rule` | `#D8C8B4` | `#3E3630` | 細線、卡片邊框 |
| `--rule-strong` | `#1C1917` | `#F3EBE1` | 區塊分隔線 |
| `--accent` | `#0B5D66` | `#7CC6C8` | 互動、引用、進度 |
| `--accent-soft` | `#DCEBE8` | `#1D3739` | badge 預設底色 |
| `--on-accent` | `#FFFFFF` | `#0F1A1B` | 主色底上的文字 |
| `--kicker` | `#8A1538` | `#E894AB` | 欄目小標（「你的問題」等） |
| `--ok` | `#2E6A39` | `#86C994` | 通過、已驗證 |
| `--ok-soft` | `#DDEBDD` | `#1E3322` | 通過的淡底 |
| `--warn` | `#7A5000` | `#E7BC5E` | 警告、驗證失敗、相關度不足 |
| `--warn-soft` | `#F6E5BF` | `#3A2E13` | 警告的淡底 |
| `--err` | `#A12A2A` | `#F09088` | 錯誤 |
| `--err-soft` | `#F6DCD8` | `#3F1F1D` | 錯誤的淡底 |
| `--band` | `#1E2A2E` | `#0E1517` | 頁首資訊帶、全文面板標題列 |
| `--on-band` | `#F6EEE3` | `#F3EBE1` | 深色帶上的文字 |
| `--band-ink2` | `#B9C6C8` | `#9FB1B3` | 深色帶上的次要文字 |
| `--shadow` | `rgba(28,25,23,0.28)` | `rgba(0,0,0,0.75)` | 只用在全文面板上緣：`box-shadow: 0 -16px 36px -10px var(--shadow)` |
| `--scrim` | `rgba(28,25,23,0.45)` | `rgba(0,0,0,0.6)` | 手機抽屜的遮罩 |

畫板的樣式表裡還有 `--mark`（黃色），目前沒有任何畫板使用，不要用它做高亮。

### 字體

字型：Noto Serif TC（500／700／900）、Noto Sans TC（400／500／700）、IBM Plex Mono（400／500）。數字一律 `font-variant-numeric: tabular-nums`。

| 用途 | 字體 | 桌面 | 手機 |
|---|---|---|---|
| 首頁刊頭 | Serif 900 | 42px，字距 0.12em | 22px |
| 內頁產品名稱 | Serif 900 | 26px，字距 0.1em | 18px |
| 頁面主標（h1） | Serif 700 | 52px（首頁）、44px（評估、關於）、40px（你的問題） | 30px（首頁）、26px（你的問題） |
| 區塊標題（h2） | Serif 700 | 24–28px | 20px |
| 答案內文 | Serif | 21px，行高 2.0 | 18px，行高 1.95 |
| 條文原文 | Serif | 卡片 16px／1.9；全文面板 17px／2.0 | 抽屜 17px／2.0 |
| 介面內文 | Sans 400 | 16px，行高 1.7 | 15px，行高 1.7 |
| 欄目小標 | Sans 700 | 14px，`--kicker` | 13px |
| 區段標籤 | Sans 700 | 15px，字距 0.3em | 13–14px |
| 資料、分數、耗時 | Plex Mono | 12–13px | 12–13px |

### 間距、線條、形狀

- 間距：4、8、16（手機邊距）、24、32（桌面邊距）、40（欄距）、56。
- 圓角一律 0；除了全文面板上緣，其他地方不使用陰影。
- 線條：區塊標題上方 3px 實線；欄間與列表 1px 細線；區段分隔 3px 點線。
- 可點元件最小高度 44px（行內的 CitationBadge 為 28px）。
- 鍵盤 focus：3px `--ink` 外框，間距 2px。

---

## 4. 畫板之間不一致時，以誰為準

| 項目 | 不一致的地方 | 以誰為準 |
|---|---|---|
| ArticleCard 的「長條文收合／展開全文」 | `Components.dc.html` ArticleCard 第一排第 4 張仍有這個狀態 | **不做**。卡片只放摘要，全文在面板或抽屜（spec 5.5-D） |
| 「高亮」的說法 | `Components.dc.html` 的 badge 標籤寫「active（對應條文高亮）」 | active 的樣式是：badge 填滿主色、卡片主色外框、底色維持 `--surface`，沒有黃色底 |
| 未被引用卡片的邊框 | `Streaming.dc.html` 是實線，`Answer.dc.html` 與 `Components.dc.html` 是虛線 | 虛線 |
| 陰影 | 原則是不使用陰影，`ArticlePanel.dc.html` 的面板上緣有陰影 | 已確認保留，面板是唯一例外（spec 5.5-H） |
| 產品名稱 | 已統一為「交通法規資料庫」 | 若在畫板的 `<title>` 或畫板標題看到「交通法規問答」，那只是畫板名稱，畫面上以「交通法規資料庫」為準 |
| 「查看全文」的行為 | `Answer.dc.html`、`AnswerDark.dc.html` 的卡片標題與「查看全文」是連到另一張畫板的連結 | 那只是畫板間的導覽。實際行為是在同一頁開啟下方面板，照 `ArticlePanel.dc.html` |
| 依據欄是否固定 | `Answer.dc.html` 的依據欄是 sticky，`ArticlePanel.dc.html` 不是 | sticky；面板開啟時以頁面區能完整捲動為優先 |
| 未被引用的標籤文字 | 依據卡片寫「檢索到」，檢索結果列表與手機依據列表寫「未引用」 | 各自沿用所在畫板的文字 |
| 範例題目 | 桌面主流程用「酒駕」（§35、§114、§35-1），手機與元件頁用「紅燈右轉」（§53、§206、§102） | 都是示意資料，沒有先後之分 |
| PipelineSteps 的兩種密度 | `Streaming.dc.html`、`Answer.dc.html` 每步有摘要文字與耗時；`Refusal.dc.html`、`Components.dc.html` 只有符號與步驟名稱 | 問答結果頁的檢索過程用完整版；拒答頁的「為什麼不回答」用精簡版。各狀態的符號與線條樣式看 `Components.dc.html` |
| ExampleQuestions 的樣式 | `Main.dc.html` 是三欄卡片（分類小標＋問題），`Components.dc.html` 是外框 chip | 首頁照 `Main.dc.html`；chip 樣式用在拒答頁的改問建議 |
| 首頁標題文字 | `Main.dc.html` 是「交通法規白話文搜尋」，`MobileHome.dc.html` 是「用白話問交通法規，每個答案都附上條文依據。」 | **桌面為準，手機也用「交通法規白話文搜尋」**（設計決定，2026-10-08） |
| 首頁刊頭 | `Main.dc.html` 新版沒有「交通法規資料庫」那一列，主選單右端是 GitHub 圖示；`MobileHome.dc.html` 仍有產品名稱與選單鈕 | 桌面照新版（另外保留外觀切換按鈕）；GitHub 圖示先不顯示，因為 repo 還沒公開（`Header.tsx` 的 `SHOW_GITHUB_LINK`，公開後改成 true）；手機保留產品名稱那一列，因為選單鈕在裡面。其他頁面與狀態的精簡頁首不變 |
| 收錄範圍 | `Main.dc.html` 新版是五欄表格（類別、法規名稱、簡稱、條文數、最新異動）；沒有手機畫板 | 桌面照表格；手機每部法規一塊（類別與名稱在上，簡稱、條文數、日期並排在下） |
| 全文面板的操作提示 | 畫板沒有 | 面板列加「按 Esc 可關閉面板」（設計 review 要求，2026-10-08） |

這張表沒有列到的不一致，先問，不自行決定。

---

## 5. 設計稿沒有的畫面

平板版面、手機的串流中畫面、手機選單內容、暗色模式切換都沒有畫板，先照 spec 5.5-G 的預設實作。React Flow 節點圖已決定延後，不在本專案範圍。
