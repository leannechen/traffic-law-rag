import type { AskEvent } from './types/events'

export const RUN = 'run-1'

export function ev<T extends AskEvent['type']>(
  type: T,
  data: Extract<AskEvent, { type: T }>['data'],
): AskEvent {
  return { type, run_id: RUN, ts: 0, data } as AskEvent
}

export function sseText(events: AskEvent[]): string {
  return events.map((e) => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`).join('')
}

/** 把文字切成固定長度的位元組片段，模擬網路把串流切在任意位置。 */
export function byteStream(text: string, chunkSize = 7): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(text)
  let offset = 0
  return new ReadableStream({
    pull(controller) {
      if (offset >= bytes.length) return controller.close()
      controller.enqueue(bytes.slice(offset, offset + chunkSize))
      offset += chunkSize
    },
  })
}

export function sseResponse(events: AskEvent[], chunkSize?: number): Response {
  return new Response(byteStream(sseText(events), chunkSize), {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

export const item = (chunkId: string, rank: number, score: number, articleNo = '53') => ({
  chunk_id: chunkId,
  pcode: 'K0040012',
  law_name: '道路交通管理處罰條例',
  law_short_name: '道交處罰條例',
  article_no: articleNo,
  score,
  snippet: `測試條文摘要 ${chunkId}`,
  rank,
  source_url: 'https://example.test/law',
  amended_date: '2000-01-01',
})

export const META = {
  data_version: '2000-01-01',
  built_at: '2000-01-01T00:00:00Z',
  embedding_model: 'test',
  chunk_count: 2,
  laws: [
    {
      pcode: 'K0040012',
      law_name: '道路交通管理處罰條例',
      law_short_name: '道交處罰條例',
      law_level: '法律' as const,
      article_count: 1,
      chunk_count: 1,
      amended_date: '2000-01-01',
    },
  ],
}

/** 一般回答的完整事件序列（和後端 spec 5.3 相同順序） */
export function normalRun(): AskEvent[] {
  return [
    ev('run.started', { question: '問題' }),
    ev('step.started', { step: 'rewrite' }),
    ev('step.completed', { step: 'rewrite', duration_ms: 0, summary: '未啟用' }),
    ev('step.started', { step: 'retrieve' }),
    ev('retrieval.results', {
      items: [
        item('K0040012:53', 1, 0.7),
        item('K0040012:35-p1', 2, 0.6, '35'),
        item('K0040012:35-p2', 3, 0.65, '35'),
      ],
    }),
    ev('step.completed', { step: 'retrieve', duration_ms: 200, summary: 'top 3' }),
    ev('step.started', { step: 'gate' }),
    ev('step.completed', { step: 'gate', duration_ms: 0, summary: '通過' }),
    ev('step.started', { step: 'generate' }),
    ev('answer.delta', { text: '**重點**依規定罰' }),
    ev('answer.delta', { text: '六百元[[K0040012:53]]。' }),
    ev('answer.citation', { marker: '[[K0040012:53]]', chunk_id: 'K0040012:53' }),
    ev('step.completed', { step: 'generate', duration_ms: 1000, summary: '1 個引用' }),
    ev('step.started', { step: 'validate' }),
    ev('validate.result', { valid: ['K0040012:53'], invalid: [] }),
    ev('step.completed', { step: 'validate', duration_ms: 0, summary: '1 / 1 通過' }),
    ev('run.completed', { total_ms: 1300 }),
  ]
}
