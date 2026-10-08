# 資料格式（全國法規資料庫開放資料）

依據 2026-10-05 下載的資料（`data_version = 2026-10-05`，XML 標示的更新時間為 2026/9/24）。
資料集：data.gov.tw 18289（法律）、18290（命令），授權為「政府資料開放授權條款－第 1 版」。

## 檔案

| ZIP | 內容 | 大小（解壓後） | 法規數 |
|---|---|---|---|
| `law.zip`（法律） | `FalV.xml`、`schema.csv`、`manifest.csv` | 25 MB | 1,347 |
| `order.zip`（命令） | `MingLing.xml`、`schema.csv`、`manifest.csv` | 112 MB | 10,451 |

## XML 結構

```
<LAWS UpdateDate="2026/9/24 上午 12:00:00">
  <法規>
    <法規性質>法律|命令|憲法…</法規性質>
    <法規名稱> / <法規網址>（網址含 pcode）/ <最新異動日期>（YYYYMMDD）
    <廢止註記>（空白＝現行；「廢」＝已廢止）
    <附件>（<檔案> 底下只有檔名與下載網址）
    <法規內容>
      <編章節>   第 一 章 總則</編章節>
      <條文><條號>第 53 條</條號><條文內容><![CDATA[…]]></條文內容></條文>
      …
```

`<編章節>` 與 `<條文>` 是同一層的兄弟節點：章節標題出現在它底下那些條文之前，所以要依順序掃描才知道一條條文屬於哪一章。

## 原始條文範例

道路交通管理處罰條例第 53 條（原樣，CDATA 內的換行就是「項」的分隔）：

```xml
<條文>
  <條號>第 53 條</條號>
  <條文內容><![CDATA[汽車駕駛人，行經有燈光號誌管制之交岔路口闖紅燈者，處新臺幣一千八百元以上五千四百元以下罰鍰。
前項紅燈右轉行為者，處新臺幣六百元以上一千八百元以下罰鍰。]]></條文內容>
</條文>
```

## 逐項確認（spec Step 2 要求）

| 問題 | 結論 | parse 的處理 |
|---|---|---|
| 項、款是否已分開？ | **沒有分開**。沒有任何標記，一項就是一行（`\n` 分隔）。款以「一、」「（一）」開頭，與前一項在同一個 `<條文內容>` 裡 | 依換行切成 `paragraphs`；「一、」「（一）」開頭的行併回前一項，其餘換行才算新的一項 |
| 「條之一」怎麼表示？ | 條號為 `第 35-1 條`（連字號），不是「條之一」。所有目標法規的條號都符合 `第 N 條` 或 `第 N-M 條` | 正規化成 `35-1`，與 spec 的 `article_no` 一致；格式不符就報錯，不默默略過 |
| 附件是內容還是檔名？ | **只有檔名與下載網址**（PDF／DOC／ODT），沒有文字內容 | 不處理附件 |
| 廢止註記 | `<廢止註記>` 為「廢」的是已廢止法規 | 排除；目標清單若指到已廢止的法規會報錯 |
| 其他發現 | ① 已刪除的條文內容是 `（刪除）`，條號仍在 ② 部分法規名稱帶後綴，如 `道路交通事故處理辦法（92.09.24  訂定）` ③ 同名法規可能有廢止舊版與現行版兩筆 ④ 編章節含「章」「節」，不含更深層 | ① 排除，不產生空 chunk ② 去掉後綴 ③ 道路交通事故處理辦法取現行 `D0080090`，舊版 `K0040015` 已廢止不收 ④ `chapter` 為「章」＋「節」（若有）的組合 |

## 裁罰基準附表能否取得

**不能。** 《違反道路交通管理事件統一裁罰基準及處理細則》（D0080029）的 `<附件>` 只有一個檔案：`附表  違反道路交通管理事件統一裁罰基準表.PDF`，開放資料裡沒有表格內容。因此這個資料集只能取得該細則的 90 條**條文**，**取不到各違規行為的裁罰金額表**。

影響：問到「某違規罰多少」時，答案應以道路交通管理處罰條例的條文為準；裁罰基準的條文可補充處理程序，但不能當作金額來源。是否保留這部法規留待 Step 3 之後再評估（目前先收）。

道路交通安全規則（K0040013）也有 40 個附件，同樣只有檔名，不影響條文本身。

## 目標法規解析結果

| pcode | 法規 | 性質 | 最新異動日 | 原始條文數 | 刪除 | 有效條文數 |
|---|---|---|---|---|---|---|
| K0040012 | 道路交通管理處罰條例 | 法律 | 20260817 | 134 | 7 | 127 |
| K0040013 | 道路交通安全規則 | 命令 | 20260626 | 185 | 11 | 174 |
| D0080090 | 道路交通事故處理辦法 | 命令 | 20240217 | 15 | 0 | 15 |
| G0390060 | 強制汽車責任保險法 | 法律 | 20220615 | 56 | 0 | 56 |
| D0080029 | 違反道路交通管理事件統一裁罰基準及處理細則 | 命令 | 20260526 | 91 | 1 | 90 |

「原始條文數」含刪除條文，與網站條號總數比對時用這一欄；「有效條文數」是進入 `data/processed/` 的數量。以上數字由 `uv run python -m app.ingestion.parse` 輸出，人工抽查請對照全國法規資料庫各法規頁面。

## 重跑

```
cd backend
uv run python -m app.ingestion.fetch   # 下載到 data/raw/{今天}/，已有快取就跳過
uv run python -m app.ingestion.parse   # 讀最新的 raw，輸出 data/processed/{pcode}.json
```

`data/raw/` 不進版控；`data/processed/` 只含目標法規，其餘法規在串流解析時即丟棄。

## 索引的資料結構（`data/index/`）

`build_index` 把 chunk 寫進本機 Chroma（`data/index/`，不進版控，可由 `data/processed/` 重建）。每次整個重建，不做增量。**要看或查索引內容，請用 Chroma 的 Python API，不要直接查裡面的 `chroma.sqlite3`**：那是 Chroma 的內部格式（表名、`chroma:document` 這類鍵都不是我們定義的），升級 Chroma 後可能改變。

### Collection

| 項目 | 值 |
|---|---|
| collection 名稱 | `law_chunks` |
| 距離 | cosine（`hnsw:space`） |
| 向量 | 1024 維（`voyage-4`，型號記在 `index_meta.json`） |
| 筆數 | 489（目前；以 `index_meta.json` 的 `chunk_count` 為準） |

### 每筆資料

| Chroma 欄位 | 內容 |
|---|---|
| `id` | `chunk_id`：整條一塊為 `{pcode}:{條號}`（如 `K0040012:53`）；超過 800 字被切開時為 `{pcode}:{條號}-p{n}`（如 `K0040012:35-p2`，n 是這條的第幾塊） |
| `document` | `text`：這一塊的條文原文。給人看與給模型的全文，不用於比對 |
| `embedding` | 由 `embed_text` 算出：標頭 + 換行 + 條文原文。標頭是「法規全名 章名 第 N 條」（沒有章名就省略），如 `道路交通管理處罰條例 第 二 章 汽車 第 53 條`，讓模型知道這段文字屬於哪部法規、哪一章 |
| `metadata` | 見下表。值為 `None` 的欄位不寫入（Chroma 不接受 None） |

metadata 的 key（來自 `LawChunk`，不含 `text`、`embed_text`）：

| key | 型別 | 說明 |
|---|---|---|
| `chunk_id` | str | 同 `id` |
| `pcode` | str | 法規代碼，如 `K0040012` |
| `law_name`、`law_short_name` | str | 法規全名與簡稱（畫面上用簡稱） |
| `law_level` | str | `法律` 或 `命令` |
| `article_no` | str | 條號，可含連字號，如 `8-1`、`39-3` |
| `paragraph_no` | int | 這一塊從第幾項開始；**整條一塊時沒有這個 key** |
| `chapter` | str | 章名；沒有章時沒有這個 key |
| `source_url` | str | 全國法規資料庫該條的網址（只當連結，我們不抓取該網站） |
| `amended_date` | str | 該法規最新異動日，`YYYYMMDD` |
| `data_version` | str | 資料版本（下載日），如 `2026-10-05` |

「條」的識別碼 `article_id` 是 `{pcode}:{條號}`（去掉 `-p{n}`），引用與全文面板都以它為單位；它不是 metadata 欄位，由 `chunk_id` 推得。

### 旁邊的 `index_meta.json`

同一個目錄下，記錄 `data_version`、`built_at`、`embedding_model`、`chunk_count`，以及每部法規的條數與 chunk 數。`/api/meta` 由它讀出。

### 怎麼查（在 `backend/`）

```python
import chromadb
from app.core.config import get_settings

collection = chromadb.PersistentClient(path=str(get_settings().index_dir)).get_collection("law_chunks")
print(collection.count())

# 取特定 chunk 的原文與 metadata
r = collection.get(ids=["K0040012:35-p2"], include=["documents", "metadatas"])

# 某部法規的全部 chunk（依 metadata 過濾）
r = collection.get(where={"pcode": "K0040012"}, include=["metadatas"])
```

統計各法規 chunk 數、被切成多塊的條文，直接跑 `uv run python -m app.ingestion.build_index` 的輸出，或看 `index_meta.json`。
