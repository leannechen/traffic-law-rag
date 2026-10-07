import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import { ev, item, META, normalRun, sseResponse } from './test-utils'
import type { AskEvent } from './types/events'

afterEach(() => vi.unstubAllGlobals())

function json(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers })
}

function stubFetch(ask: () => Response | Promise<Response>) {
  const fetchMock = vi.fn((url: string) =>
    url === '/api/meta' ? Promise.resolve(json(META)) : Promise.resolve(ask()),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderApp(path = '/') {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function ask(question: string) {
  const user = userEvent.setup()
  await user.type(screen.getByRole('textbox', { name: '你的問題' }), question)
  await user.click(screen.getByRole('button', { name: /提問/ }))
  return user
}

/** 串流一直不結束的回應：先送出 first，再等到測試結束。 */
function openStream(first: AskEvent[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const e of first) {
        controller.enqueue(encoder.encode(`event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`))
      }
    },
  })
  return new Response(body, { status: 200 })
}

describe('home', () => {
  it('shows the product name, examples and the scope from /api/meta', async () => {
    stubFetch(() => json({}))
    renderApp()
    expect(screen.getByRole('link', { name: '交通法規資料庫' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /紅燈右轉會被罰多少錢/ })).toHaveLength(1)
    expect(await screen.findByRole('heading', { name: '道路交通管理處罰條例' })).toBeInTheDocument()
  })

  it('disables submit and shows an error beyond 200 characters', async () => {
    stubFetch(() => json({}))
    renderApp()
    const input = screen.getByRole('textbox', { name: '你的問題' })
    await userEvent.setup().click(input)
    await userEvent.setup().paste('字'.repeat(201))
    expect(screen.getByText(/問題超過 200 字/)).toBeInTheDocument()
    expect(screen.getByText('201 / 200')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /提問/ })).toBeDisabled()
  })

  it('does not submit an empty question; the button just returns focus to the input', async () => {
    const fetchMock = stubFetch(() => json({}))
    renderApp()
    const button = screen.getByRole('button', { name: /提問/ })
    expect(button).toBeEnabled() // 畫板：空白時按鈕和平常一樣
    await userEvent.setup().click(button)
    expect(screen.getByRole('textbox', { name: '你的問題' })).toHaveFocus()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/ask', expect.anything())
  })
})

describe('asking', () => {
  it('streams an answer with citation, evidence ordered cited-first, and a restart button', async () => {
    const fetchMock = stubFetch(() => sseResponse(normalRun(), 13))
    renderApp()
    await ask('紅燈右轉會被罰多少錢？')

    expect(await screen.findByRole('button', { name: '重新提問' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('紅燈右轉會被罰多少錢？')
    const answer = screen.getByRole('region', { name: '答案' })
    expect(answer).toHaveTextContent('依規定罰六百元')
    expect(answer).not.toHaveTextContent('[[')
    expect(answer).not.toHaveTextContent('**')
    expect(within(answer).getByText('道交處罰條例 §53')).toBeInTheDocument()

    const evidence = screen.getByRole('complementary', { name: '依據' })
    expect(evidence).toHaveTextContent('已引用 1 · 檢索到 2')
    const titles = within(evidence)
      .getAllByRole('heading', { level: 3 })
      .map((h) => h.textContent)
    expect(titles).toEqual(['道交處罰條例 第 53 條', '道交處罰條例 第 35 條'])
    expect(fetchMock).toHaveBeenCalledWith('/api/ask', expect.objectContaining({ method: 'POST' }))
  })

  it('has nothing clickable in the answer or evidence while streaming, and stop shows the stopped state', async () => {
    stubFetch(() =>
      openStream([
        ev('run.started', { question: 'Q' }),
        ev('step.started', { step: 'retrieve' }),
        ev('retrieval.results', { items: [item('K0040012:53', 1, 0.7)] }),
        ev('answer.delta', { text: '先回答一半[[K0040012:53]]' }),
      ]),
    )
    renderApp()
    const user = await ask('紅燈右轉會被罰多少錢？')

    const answer = await screen.findByRole('region', { name: '答案' })
    await waitFor(() => expect(answer).toHaveTextContent('先回答一半'))
    expect(within(answer).queryAllByRole('button')).toHaveLength(0)
    expect(within(answer).queryAllByRole('link')).toHaveLength(0)
    const evidence = screen.getByRole('complementary', { name: '依據' })
    expect(within(evidence).queryAllByRole('button')).toHaveLength(0)
    expect(within(evidence).queryAllByRole('link')).toHaveLength(0)
    expect(screen.getByText('正在產生答案…')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '停止' }))
    expect(await screen.findByText('你已停止產生，答案不完整')).toBeInTheDocument()
    expect(answer).toHaveTextContent('先回答一半')
    expect(screen.queryByRole('button', { name: '停止' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新產生' })).toBeInTheDocument()
  })

  it('shows the refusal notice and the scope aside', async () => {
    stubFetch(() =>
      sseResponse([
        ev('run.started', { question: 'Q' }),
        ev('answer.refused', { reason: 'low_relevance', top_score: 0.26, threshold: 0.4 }),
        ev('run.completed', { total_ms: 264 }),
      ]),
    )
    renderApp()
    await ask('今天天氣怎麼樣？')

    expect(await screen.findByText('資料範圍內找不到相關規定')).toBeInTheDocument()
    expect(screen.getByText('0.26 ＜ 門檻 0.40')).toBeInTheDocument()
    expect(screen.getByText('為什麼不回答')).toBeInTheDocument()
    expect(screen.getByRole('complementary', { name: '收錄範圍' })).toHaveTextContent(
      '道路交通管理處罰條例',
    )
    expect(screen.queryByRole('region', { name: '答案' })).not.toBeInTheDocument()
  })

  it('shows an interruption error when the stream ends without completing', async () => {
    stubFetch(() =>
      sseResponse([ev('run.started', { question: 'Q' }), ev('answer.delta', { text: '一半' })]),
    )
    renderApp()
    await ask('紅燈右轉會被罰多少錢？')

    expect(await screen.findByText('答案沒有完整送達')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('stream_interrupted')
    expect(screen.getByRole('region', { name: '答案' })).toHaveTextContent('一半')
  })

  it('shows a server error event as an error notice', async () => {
    stubFetch(() =>
      sseResponse([
        ev('run.started', { question: 'Q' }),
        ev('error', { code: 'llm_error', message: '回答服務暫時無法使用' }),
      ]),
    )
    renderApp()
    await ask('紅燈右轉會被罰多少錢？')
    expect(await screen.findByText('回答服務暫時無法使用', { selector: 'h2' })).toBeInTheDocument()
  })

  it('shows a rate limit countdown and disables retry until it ends', async () => {
    stubFetch(() => json({ detail: '請求太頻繁，請稍後再試' }, 429, { 'Retry-After': '42' }))
    renderApp()
    await ask('紅燈右轉會被罰多少錢？')

    expect(await screen.findByText('提問太頻繁，請稍後再試')).toBeInTheDocument()
    expect(screen.getByText(/00:4[12] 後可再提問/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重試' })).toBeDisabled()
  })

  it('starts a new run from the restart button', async () => {
    stubFetch(() => sseResponse(normalRun()))
    renderApp()
    const user = await ask('紅燈右轉會被罰多少錢？')
    await user.click(await screen.findByRole('button', { name: '重新提問' }))
    expect(await screen.findByRole('textbox', { name: '你的問題' })).toHaveValue('')
  })
})

describe('review fixes', () => {
  it('has no tabbable element in the answer or evidence while streaming', async () => {
    stubFetch(() =>
      openStream([
        ev('retrieval.results', { items: [item('K0040012:53', 1, 0.7)] }),
        ev('answer.delta', { text: '回答中[[K0040012:53]]' }),
      ]),
    )
    renderApp()
    await ask('紅燈右轉會被罰多少錢？')
    const answer = await screen.findByRole('region', { name: '答案' })
    await waitFor(() => expect(answer).toHaveTextContent('回答中'))
    const evidence = screen.getByRole('complementary', { name: '依據' })
    for (const area of [answer, evidence]) {
      expect(area.querySelectorAll('a, button, input, textarea, select, [tabindex]')).toHaveLength(
        0,
      )
    }
  })

  it('does not submit when Enter confirms an IME composition (Safari keyCode 229)', async () => {
    const fetchMock = stubFetch(() => sseResponse(normalRun()))
    renderApp()
    const input = screen.getByRole('textbox', { name: '你的問題' })
    await userEvent.setup().type(input, '紅燈')
    fireEvent.keyDown(input, { key: 'Enter', keyCode: 229 })
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true })
    expect(fetchMock).not.toHaveBeenCalledWith('/api/ask', expect.anything())
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/ask',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })

  it('goes back to the home scope section from another page even with a result open', async () => {
    stubFetch(() => sseResponse(normalRun()))
    renderApp()
    const user = await ask('紅燈右轉會被罰多少錢？')
    await screen.findByRole('button', { name: '重新提問' })
    await user.click(screen.getByRole('link', { name: '關於' }))
    await user.click(screen.getByRole('link', { name: '收錄範圍' }))
    expect(await screen.findByRole('heading', { name: '收錄範圍' })).toBeInTheDocument()
  })

  it('offers no retry button for an invalid question', async () => {
    stubFetch(() => json({ detail: [{ msg: '問題不能超過 200 字' }] }, 422))
    renderApp()
    await ask('紅燈')
    expect(await screen.findByText('問題格式不符')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重試' })).not.toBeInTheDocument()
  })

  it('hides process and evidence when the run failed', async () => {
    stubFetch(() =>
      sseResponse([
        ev('retrieval.results', { items: [item('K0040012:53', 1, 0.7)] }),
        ev('error', { code: 'llm_error', message: 'x' }),
      ]),
    )
    renderApp()
    await ask('紅燈右轉會被罰多少錢？')
    await screen.findByRole('alert')
    expect(screen.queryByRole('complementary', { name: '依據' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '檢索過程' })).not.toBeInTheDocument()
  })

  it('shows only the article number for a citation outside the retrieved evidence', async () => {
    stubFetch(() =>
      sseResponse([
        ev('retrieval.results', { items: [item('K0040012:53', 1, 0.7)] }),
        ev('answer.delta', { text: '亂引用[[K9999999:77]]' }),
        ev('run.completed', { total_ms: 1 }),
      ]),
    )
    renderApp()
    await ask('紅燈右轉會被罰多少錢？')
    const answer = await screen.findByRole('region', { name: '答案' })
    await waitFor(() => expect(answer).toHaveTextContent('§77'))
    expect(answer).not.toHaveTextContent('K9999999')
  })
})

describe('wrong backend', () => {
  it('explains a 404 from /api/ask as a probable wrong BACKEND_URL', async () => {
    stubFetch(() => json({ detail: 'Not Found' }, 404))
    renderApp()
    await ask('紅燈右轉會被罰多少錢？')
    expect(await screen.findByText('伺服器沒有回應預期的內容')).toBeInTheDocument()
    expect(screen.getByText(/BACKEND_URL/)).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('HTTP 404')
  })

  it('says the service is not ready for a 503', async () => {
    stubFetch(() => json({ detail: '索引尚未建立' }, 503))
    renderApp()
    await ask('紅燈右轉會被罰多少錢？')
    expect(await screen.findByText('問答服務暫時無法使用')).toBeInTheDocument()
  })
})

describe('routes', () => {
  it('renders the about page', async () => {
    stubFetch(() => json({}))
    renderApp('/about')
    expect(screen.getByRole('heading', { level: 1, name: /只根據條文回答/ })).toBeInTheDocument()
    expect(await screen.findByText(/目前版本為 2000-01-01/)).toBeInTheDocument()
  })

  it('renders the eval page placeholder', () => {
    stubFetch(() => json({}))
    renderApp('/eval')
    expect(screen.getByRole('heading', { name: '評估結果' })).toBeInTheDocument()
  })
})
