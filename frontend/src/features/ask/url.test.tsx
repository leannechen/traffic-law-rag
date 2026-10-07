import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider, useLocation } from 'react-router-dom'
import App from '../../App'
import { ev, META, normalRun, sseResponse } from '../../test-utils'

afterEach(() => vi.unstubAllGlobals())

function Probe() {
  const { pathname, search } = useLocation()
  return <output aria-label="網址">{`${pathname}${decodeURIComponent(search)}`}</output>
}

function setup(path = '/') {
  const fetchMock = vi.fn((url: string) =>
    url === '/api/meta'
      ? Promise.resolve(new Response(JSON.stringify(META)))
      : Promise.resolve(sseResponse(normalRun())),
  )
  vi.stubGlobal('fetch', fetchMock)
  const router = createMemoryRouter(
    [
      {
        path: '*',
        element: (
          <>
            <App />
            <Probe />
          </>
        ),
      },
    ],
    { initialEntries: [path] },
  )
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  const asks = () =>
    fetchMock.mock.calls.filter(([url]) => url === '/api/ask') as unknown as [string, RequestInit][]
  return { router, asks }
}

const url = () => screen.getByLabelText('網址')

describe('question in the URL', () => {
  it('puts the question into the URL when asking, and clears it on 重新提問', async () => {
    setup()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('你的問題'), '紅燈右轉會被罰多少錢？')
    await user.click(screen.getByRole('button', { name: /提問/ }))
    await screen.findByRole('button', { name: '重新提問' })
    expect(url()).toHaveTextContent('/?q=紅燈右轉會被罰多少錢？')

    await user.click(screen.getByRole('button', { name: '重新提問' }))
    expect(url()).toHaveTextContent(/^\/$/)
    expect(screen.getByLabelText('你的問題')).toHaveValue('')
  })

  it('asks immediately when the page is opened with ?q= (reload or shared link)', async () => {
    const { asks } = setup('/?q=酒駕被抓到會有什麼處罰？')
    expect(await screen.findByRole('button', { name: '重新提問' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('酒駕被抓到會有什麼處罰？')
    expect(asks()).toHaveLength(1)
    const body = JSON.parse(asks()[0][1].body as string)
    expect(body).toEqual({ question: '酒駕被抓到會有什麼處罰？' })
    expect(document.title).toBe('酒駕被抓到會有什麼處罰？｜交通法規資料庫')
  })

  it('browser back returns to the home page, forward asks the question again', async () => {
    const { router, asks } = setup()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /紅燈右轉會被罰多少錢/ }))
    await screen.findByRole('button', { name: '重新提問' })

    await router.navigate(-1)
    await waitFor(() => expect(screen.getByLabelText('你的問題')).toBeInTheDocument())
    expect(url()).toHaveTextContent(/^\/$/)

    await router.navigate(1)
    await screen.findByRole('button', { name: '重新提問' })
    expect(asks()).toHaveLength(2)
  })

  it('a different question from the refusal page is a new history entry', async () => {
    const refusal = () =>
      sseResponse([
        ev('run.started', { question: 'Q' }),
        ev('answer.refused', { reason: 'low_relevance', top_score: 0.2, threshold: 0.4 }),
        ev('run.completed', { total_ms: 1 }),
      ])
    const fetchMock = vi.fn((u: string, init?: RequestInit) => {
      if (u === '/api/meta') return Promise.resolve(new Response(JSON.stringify(META)))
      const asked = JSON.parse(String(init?.body)).question as string
      return Promise.resolve(asked.includes('天氣') ? refusal() : sseResponse(normalRun()))
    })
    vi.stubGlobal('fetch', fetchMock)
    const router = createMemoryRouter(
      [
        {
          path: '*',
          element: (
            <>
              <App />
              <Probe />
            </>
          ),
        },
      ],
      { initialEntries: ['/?q=今天天氣怎麼樣？'] },
    )
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: '紅燈右轉會被罰多少錢？' }))
    await screen.findByRole('button', { name: '重新提問' })
    expect(url()).toHaveTextContent('/?q=紅燈右轉會被罰多少錢？')
    await router.navigate(-1)
    expect(await screen.findByText('資料範圍內找不到相關規定')).toBeInTheDocument()
  })

  it('retrying the same question does not add a history entry', async () => {
    const { router, asks } = setup('/?q=紅燈右轉會被罰多少錢？')
    await screen.findByRole('button', { name: '重新提問' })
    const before = router.state.historyAction
    expect(asks()).toHaveLength(1)
    expect(before).toBe('POP')
  })

  it('keeps the running answer while visiting another page and coming back', async () => {
    const { router, asks } = setup('/?q=紅燈右轉會被罰多少錢？')
    await screen.findByRole('button', { name: '重新提問' })
    await router.navigate('/about')
    await router.navigate(-1)
    expect(await screen.findByRole('button', { name: '重新提問' })).toBeInTheDocument()
    expect(asks()).toHaveLength(1) // 沒有重新提問
  })
})
