import { byteStream, ev, normalRun, sseText } from '../test-utils'
import { AskHttpError, parseSseBlock, readSse, streamAsk } from './sse'

afterEach(() => vi.unstubAllGlobals())

async function collect<T>(gen: AsyncGenerator<T>): Promise<T[]> {
  const out: T[] = []
  for await (const x of gen) out.push(x)
  return out
}

describe('parseSseBlock', () => {
  it('reads event and data fields', () => {
    expect(parseSseBlock('event: answer.delta\ndata: {"a":1}')).toEqual({
      event: 'answer.delta',
      data: '{"a":1}',
    })
  })

  it('ignores heartbeat comments', () => {
    expect(parseSseBlock(': heartbeat')).toBeNull()
  })

  it('joins multi-line data', () => {
    expect(parseSseBlock('data: a\ndata: b')?.data).toBe('a\nb')
  })
})

describe('readSse', () => {
  it('reassembles messages split at every possible byte boundary', async () => {
    const text = sseText([ev('answer.delta', { text: '紅燈右轉[[K0040012:53]]罰六百元' })])
    for (let size = 1; size <= 9; size++) {
      const messages = await collect(readSse(byteStream(text, size)))
      expect(messages).toHaveLength(1)
      expect(JSON.parse(messages[0].data).data.text).toBe('紅燈右轉[[K0040012:53]]罰六百元')
    }
  })

  it('skips heartbeat comments between events and handles CRLF', async () => {
    const text = ': heartbeat\n\nevent: a\r\ndata: 1\r\n\r\n: heartbeat\n\nevent: b\ndata: 2\n\n'
    const messages = await collect(readSse(byteStream(text, 5)))
    expect(messages.map((m) => m.event)).toEqual(['a', 'b'])
  })

  it('yields a final message that has no trailing blank line', async () => {
    const messages = await collect(readSse(byteStream('event: a\ndata: 1', 4)))
    expect(messages).toEqual([{ event: 'a', data: '1' }])
  })
})

describe('streamAsk', () => {
  it('yields typed events in order and sends the question as JSON', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(byteStream(sseText(normalRun()), 11), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const events = await collect(streamAsk('紅燈右轉？', new AbortController().signal))
    expect(events.map((e) => e.type)[0]).toBe('run.started')
    expect(events.at(-1)?.type).toBe('run.completed')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/ask')
    expect(JSON.parse(init.body)).toEqual({ question: '紅燈右轉？' })
  })

  it('skips events it does not recognise instead of failing', async () => {
    const text = 'event: future\ndata: {"type":"future","data":{}}\n\nevent: x\ndata: not json\n\n'
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(byteStream(text), { status: 200 })),
    )
    expect(await collect(streamAsk('q', new AbortController().signal))).toEqual([])
  })

  it('turns 429 into AskHttpError with Retry-After', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: '請求太頻繁，請稍後再試' }), {
          status: 429,
          headers: { 'Retry-After': '42' },
        }),
      ),
    )
    const error = await collect(streamAsk('q', new AbortController().signal)).catch((e) => e)
    expect(error).toBeInstanceOf(AskHttpError)
    expect(error).toMatchObject({ status: 429, retryAfter: 42, detail: '請求太頻繁，請稍後再試' })
  })

  it('reads the message of a 422 validation error', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: [{ msg: 'too long' }] }), { status: 422 }),
        ),
    )
    const error = await collect(streamAsk('q', new AbortController().signal)).catch((e) => e)
    expect(error).toMatchObject({ status: 422, detail: 'too long', retryAfter: null })
  })
})
