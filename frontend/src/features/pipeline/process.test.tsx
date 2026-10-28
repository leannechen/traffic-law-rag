import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import App from '../../App'
import { ev, item, META, normalRun, sseResponse } from '../../test-utils'
import type { AskEvent } from '../../types/events'

afterEach(() => vi.unstubAllGlobals())

function setup(events: AskEvent[], mobile = false) {
  window.matchMedia = ((query: string) => ({
    matches: mobile && query.includes('max-width: 767px'),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve(
        url === '/api/meta' ? new Response(JSON.stringify(META)) : sseResponse(events),
      ),
    ),
  )
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function ask() {
  const user = userEvent.setup()
  await user.type(screen.getByRole('textbox', { name: '你的問題' }), '紅燈右轉會被罰多少錢？')
  await user.click(screen.getByRole('button', { name: /提問/ }))
  return user
}

const processToggle = () => screen.getByRole('button', { name: /檢索過程/ })

describe('檢索過程 (desktop)', () => {
  it('stays expanded when the answer completes, and can be collapsed and expanded', async () => {
    setup(normalRun())
    const user = await ask()
    await screen.findByRole('button', { name: '重新提問' })

    expect(processToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(processToggle()).toHaveTextContent('✓ 5 個步驟完成 · 檢索到 2 條 · 1.3 秒')
    const steps = screen.getByRole('list', { name: '處理步驟' })
    expect(within(steps).getAllByRole('listitem')).toHaveLength(5)
    expect(steps).toHaveTextContent('改寫問題')
    expect(steps).toHaveTextContent('未啟用')
    expect(steps).toHaveTextContent('0.2s')

    await user.click(processToggle())
    expect(processToggle()).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('list', { name: '處理步驟' })).not.toBeInTheDocument()

    await user.click(processToggle())
    expect(processToggle()).toHaveAttribute('aria-expanded', 'true')
  })

  it('shows the retrieval results with citation tags only after completion', async () => {
    setup(normalRun())
    await ask()
    await screen.findByRole('button', { name: '重新提問' })
    const panel = screen.getByRole('heading', { name: '檢索結果' }).parentElement?.parentElement
    expect(panel).toHaveTextContent('道交處罰條例 §53')
    expect(panel).toHaveTextContent('已引用')
    expect(panel).toHaveTextContent('未引用')
    expect(panel).toHaveTextContent('0.70')
  })

  it('stays expanded and shows progress while streaming, with a skeleton before results', async () => {
    const encoder = new TextEncoder()
    const first: AskEvent[] = [
      ev('run.started', { question: 'Q' }),
      ev('step.completed', { step: 'rewrite', duration_ms: 0, summary: '未啟用' }),
      ev('step.started', { step: 'retrieve' }),
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url === '/api/meta'
            ? new Response(JSON.stringify(META))
            : new Response(
                new ReadableStream<Uint8Array>({
                  start(c) {
                    for (const e of first) {
                      c.enqueue(encoder.encode(`event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`))
                    }
                  },
                }),
              ),
        ),
      ),
    )
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await ask()
    const steps = await screen.findByRole('list', { name: '處理步驟' })
    expect(processToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(within(steps).getAllByRole('listitem')[1]).toHaveTextContent('進行中')
    expect(within(steps).getAllByRole('listitem')[4]).toHaveTextContent('等待中')
  })

  it('does not show the original question as a rewritten query when rewriting is off', async () => {
    setup([
      ev('run.started', { question: 'Q' }),
      ev('rewrite.result', { queries: ['紅燈右轉會被罰多少錢？'] }),
      ev('retrieval.results', { items: [item('K0040012:53', 1, 0.9)] }),
      ev('answer.delta', { text: '答[[K0040012:53]]' }),
      ev('validate.result', { valid: ['K0040012:53'], invalid: [] }),
      ev('run.completed', { total_ms: 1000 }),
    ])
    await ask()
    await screen.findByRole('button', { name: '重新提問' })
    expect(screen.queryByText(/改寫查詢/)).not.toBeInTheDocument()
  })

  it('shows the rewritten queries when rewriting is on', async () => {
    setup([
      ev('run.started', { question: 'Q' }),
      ev('rewrite.result', { queries: ['闖紅燈 處罰', '紅燈 右轉'] }),
      ev('retrieval.results', { items: [item('K0040012:53', 1, 0.9)] }),
      ev('answer.delta', { text: '答[[K0040012:53]]' }),
      ev('validate.result', { valid: ['K0040012:53'], invalid: [] }),
      ev('run.completed', { total_ms: 1000 }),
    ])
    await ask()
    await screen.findByRole('button', { name: '重新提問' })
    expect(screen.getByText('改寫查詢：「闖紅燈 處罰」「紅燈 右轉」')).toBeInTheDocument()
  })
})

describe('為什麼不回答', () => {
  it('shows the refusal branch: stops at the relevance check, the rest skipped, with the score comparison', async () => {
    setup([
      ev('run.started', { question: 'Q' }),
      ev('step.completed', { step: 'rewrite', duration_ms: 0, summary: '未啟用' }),
      ev('step.completed', { step: 'retrieve', duration_ms: 200, summary: 'top 5' }),
      ev('step.completed', { step: 'gate', duration_ms: 0, summary: '最高 0.26 < 門檻 0.40' }),
      ev('answer.refused', { reason: 'low_relevance', top_score: 0.26, threshold: 0.4 }),
      ev('run.completed', { total_ms: 264 }),
    ])
    await ask()
    const steps = await screen.findByRole('list', { name: '處理步驟' })
    const items = within(steps).getAllByRole('listitem')
    expect(items[2]).toHaveTextContent('相關度不足')
    expect(items[2]).toHaveTextContent('停在這一步')
    expect(items[3]).toHaveTextContent('略過')
    expect(items[4]).toHaveTextContent('略過')
    expect(screen.getByText('0.26 ＜ 門檻 0.40')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '最高相似度 0.26，門檻 0.40' })).toBeInTheDocument()
  })

  it('explains a model refusal after the gate passed', async () => {
    setup([
      ev('run.started', { question: 'Q' }),
      ev('step.completed', { step: 'rewrite', duration_ms: 0, summary: '未啟用' }),
      ev('step.completed', { step: 'retrieve', duration_ms: 1, summary: 'top 5' }),
      ev('step.completed', { step: 'gate', duration_ms: 0, summary: '最高 0.55 ≥ 門檻 0.40' }),
      ev('step.completed', { step: 'generate', duration_ms: 1700, summary: '條文不足，模型拒答' }),
      ev('answer.refused', { reason: 'out_of_scope', top_score: 0.55, threshold: 0.4 }),
      ev('run.completed', { total_ms: 1800 }),
    ])
    await ask()
    expect(await screen.findByText('0.55 ≥ 門檻 0.40')).toBeInTheDocument()
    const items = within(screen.getByRole('list', { name: '處理步驟' })).getAllByRole('listitem')
    expect(items[3]).toHaveTextContent('條文不足')
    expect(items[4]).toHaveTextContent('略過')
    expect(screen.getByText(/模型判斷這些條文不足以回答/)).toBeInTheDocument()
  })
})

describe('檢索過程 (mobile)', () => {
  it('is expanded by default in the process tab and does not auto-collapse', async () => {
    setup(normalRun(), true)
    const user = await ask()
    await screen.findByRole('button', { name: '重新提問' })
    await user.click(screen.getByRole('tab', { name: '過程與依據' }))
    expect(processToggle()).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('list', { name: '處理步驟' })).toBeInTheDocument()
    await user.click(processToggle())
    expect(screen.queryByRole('list', { name: '處理步驟' })).not.toBeInTheDocument()
  })
})
