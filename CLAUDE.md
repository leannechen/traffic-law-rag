# 交通法規問答（Traffic Law RAG）

用白話問台灣交通法規，系統只根據條文回答並標註出處。FastAPI 後端＋React 前端。這是 Leanne 的求職作品集專案。

## 先讀

- `docs/02-implementation-spec.md`：實作規格，唯一依據。依 Step 順序進行，**一次只做一個 Step**。
- `docs/design/README.md`：設計稿對照表、token、畫板不一致時以誰為準。做前端（Step 7–10）前必讀。
- `docs/01-ui-design-brief.md`：設計前的需求簡報，僅供參考，衝突時不以它為準。

## 目前進度

- 已完成：（無）
- 下一步：Step 1 專案骨架

每完成一個 Step 就更新這一段。

## 工作方式

1. 開始一個 Step 時先提出計畫（要建立或修改的檔案、資料流、測試、不確定的地方），等 Leanne 確認後才寫程式。
2. 只做該 Step 的範圍，不順手做後面的步驟。
3. 完成時逐項對照該 Step 的驗收條件，附上實際執行的指令與輸出。
4. 實際情況與 spec 不符時，先停下來回報並更新 spec 或 ADR，不自行假設後繼續。
5. 重要技術決策寫成 ADR，放 `docs/decisions/`。Leanne 需要能在面試中說明每個決策，解釋時講清楚「為什麼」與「放棄了什麼」。

## 不可違反

- 不寫任何抓取 `law.moj.gov.tw` 網頁的程式；資料只來自 data.gov.tw 的開放資料集。
- API key 只放 `.env`，不進程式與版控；`data/raw/` 不進版控。
- 評估集的標準答案（`expected_chunk_ids`、`expected_facts`）只能由 Leanne 人工確認；產生的草稿一律 `verified: false`。
- 前端以核准設計稿為準，要偏離先提出。畫板裡的條文、金額、分數、日期都是示意資料，不可寫進程式或測試。
- spec 5.5-H 的待確認項目，做到相關畫面前先問。

## 指令

Step 1 完成後把實際指令填在這裡（後端：uv、pytest、ruff、mypy；前端：Biome、tsc、Vitest；整體：docker compose）。
