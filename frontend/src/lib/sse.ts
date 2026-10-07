import { type AskEvent, parseAskEvent } from '../types/events'

export type SseMessage = { event: string; data: string }

/** 切出一個 SSE 區塊（以空行分隔）：取 event 與 data 欄位；只有註解（heartbeat）時回傳 null。 */
export function parseSseBlock(block: string): SseMessage | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line === '' || line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  return data.length === 0 ? null : { event, data: data.join('\n') }
}

/** 把位元組串流解析成 SSE 訊息。chunk 可以切在任何位置（包含多位元組字元中間）。 */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseMessage> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      buffer = buffer.replace(/\r\n?/g, '\n')
      let end = buffer.indexOf('\n\n')
      while (end !== -1) {
        const message = parseSseBlock(buffer.slice(0, end))
        buffer = buffer.slice(end + 2)
        if (message) yield message
        end = buffer.indexOf('\n\n')
      }
      if (done) break
    }
    const rest = parseSseBlock(buffer)
    if (rest) yield rest
  } finally {
    reader.releaseLock()
  }
}

/** 送出請求前就失敗（HTTP 狀態碼不是 2xx）。串流開始後的錯誤走 `error` 事件，不會用到它。 */
export class AskHttpError extends Error {
  readonly status: number
  readonly detail: string
  readonly retryAfter: number | null

  constructor(status: number, detail: string, retryAfter: number | null) {
    super(`ask request failed: ${status}`)
    this.status = status
    this.detail = detail
    this.retryAfter = retryAfter
  }
}

async function errorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
    if (Array.isArray(body?.detail) && typeof body.detail[0]?.msg === 'string') {
      return body.detail[0].msg
    }
  } catch {
    // 回應不是 JSON：沒有細節可顯示
  }
  return ''
}

/** POST /api/ask，逐個產生事件。signal 中止時 fetch 會丟 AbortError。 */
export async function* streamAsk(question: string, signal: AbortSignal): AsyncGenerator<AskEvent> {
  const res = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal,
  })
  if (!res.ok || !res.body) {
    const retryAfter = Number(res.headers.get('Retry-After'))
    throw new AskHttpError(
      res.status,
      await errorDetail(res),
      Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null,
    )
  }
  for await (const message of readSse(res.body)) {
    const event = parseAskEvent(message.data)
    if (event) yield event
  }
}
