// 對應 backend/app/schemas/meta.py（GET /api/meta）

export type LawMeta = {
  pcode: string
  law_name: string
  law_short_name: string
  law_level: '法律' | '命令'
  article_count: number
  chunk_count: number
  amended_date: string
}

export type IndexMeta = {
  data_version: string
  built_at: string
  embedding_model: string
  chunk_count: number
  laws: LawMeta[]
}
