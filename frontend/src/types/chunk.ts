// 對應 backend/app/schemas/chunk.py（GET /api/chunks/{id}）

export type ChunkDetail = {
  chunk_id: string
  article_id: string
  pcode: string
  law_name: string
  law_short_name: string
  law_level: '法律' | '命令'
  article_no: string
  paragraph_no: number | null
  chapter: string | null
  text: string
  source_url: string
  amended_date: string
  data_version: string
  /** 所屬條文的整條全文（chunk 依項切分時為各項合併） */
  article_text: string
}
