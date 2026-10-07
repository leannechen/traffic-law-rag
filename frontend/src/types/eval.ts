// 對應 backend/app/schemas/eval.py（GET /api/eval/latest）

export type Retrieval = 'hit' | 'partial' | 'miss' | 'na'
export type Citation = 'ok' | 'wrong' | 'refused_ok' | 'answered_out_of_scope' | 'false_refusal'
export type Numbers = 'ok' | 'mismatch' | 'na'

export type EvalRow = {
  id: string
  question: string
  category: string
  should_refuse: boolean
  expected: string[]
  retrieved: { article_id: string; score: number | null }[]
  retrieval: Retrieval
  first_hit_rank: number | null
  citation: Citation
  numbers: Numbers
  fact_amounts_expected: number | null
  fact_amounts_found: number | null
}

export type EvalReport = {
  name: string
  evaluated_at: string
  data_version: string
  counts: { verified: number; answerable: number; out_of_scope: number }
  metrics: {
    recall_at_5: number
    mrr: number
    citation_accuracy: number
    number_accuracy: number | null
    refusal_accuracy: number
  }
  questions: EvalRow[]
}
