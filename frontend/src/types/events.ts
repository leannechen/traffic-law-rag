// 與 backend/app/schemas/events.py 對應（spec 5.3）。外框 {type, run_id, ts, data}。

export type StepName = 'rewrite' | 'retrieve' | 'rerank' | 'gate' | 'generate' | 'validate'

export type RetrievalItem = {
  chunk_id: string
  pcode: string
  law_name: string
  law_short_name: string
  article_no: string
  score: number
  snippet: string
  rank: number
  source_url: string
  amended_date: string
}

export type RefusalReason = 'low_relevance' | 'out_of_scope'
export type ServerErrorCode = 'llm_error' | 'embedding_error' | 'internal_error' | 'truncated'

type Envelope<T extends string, D> = { type: T; run_id: string; ts: number; data: D }

export type AskEvent =
  | Envelope<'run.started', { question: string }>
  | Envelope<'step.started', { step: StepName }>
  | Envelope<'step.completed', { step: StepName; duration_ms: number; summary: string }>
  | Envelope<'rewrite.result', { queries: string[] }>
  | Envelope<'retrieval.results', { items: RetrievalItem[] }>
  | Envelope<'answer.delta', { text: string }>
  | Envelope<'answer.citation', { marker: string; chunk_id: string }>
  | Envelope<
      'answer.refused',
      { reason: RefusalReason; top_score: number | null; threshold: number }
    >
  | Envelope<'validate.result', { valid: string[]; invalid: string[] }>
  | Envelope<'run.completed', { total_ms: number }>
  | Envelope<'error', { code: ServerErrorCode; message: string }>

const EVENT_TYPES: ReadonlySet<string> = new Set([
  'run.started',
  'step.started',
  'step.completed',
  'rewrite.result',
  'retrieval.results',
  'answer.delta',
  'answer.citation',
  'answer.refused',
  'validate.result',
  'run.completed',
  'error',
])

/** 把 SSE 的 data 字串解析成事件；格式不對或不認得的 type 回傳 null（略過，不中斷串流）。 */
export function parseAskEvent(data: string): AskEvent | null {
  let value: unknown
  try {
    value = JSON.parse(data)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null) return null
  const { type, data: payload } = value as { type?: unknown; data?: unknown }
  if (typeof type !== 'string' || !EVENT_TYPES.has(type)) return null
  if (typeof payload !== 'object' || payload === null) return null
  return value as AskEvent
}
