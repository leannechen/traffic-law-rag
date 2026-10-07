import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import App from '../../App'
import { ev, item, META, sseResponse } from '../../test-utils'
import type { AskEvent } from '../../types/events'

afterEach(() => vi.unstubAllGlobals())

const ARTICLES: Record<string, string> = {
  'K0040012:53': '第五十三條全文。\n前項紅燈右轉行為者，處罰鍰。',
  'K0040012:35': '第三十五條全文，整條（含兩項）。',
  'K0040012:58': '第五十八條全文。',
}

function run(overrides: { invalid?: string[] } = {}): AskEvent[] {
  const invalid = overrides.invalid ?? []
  return [
    ev('run.started', { question: 'Q' }),
    ev('retrieval.results', {
      items: [
        item('K0040012:53', 1, 0.9, '53'),
        item('K0040012:35-p1', 2, 0.8, '35'),
        item('K0040012:58', 3, 0.7, '58'),
      ],
    }),
    ev('answer.delta', { text: '紅燈右轉罰鍰[[K0040012:53]]。酒駕另有規定[[K0040012:35]]' }),
    ev('answer.delta', { text: invalid.length ? `，並引用[[${invalid[0]}]]。` : '。' }),
    ev('validate.result', {
      valid: ['K0040012:53', 'K0040012:35'],
      invalid,
    }),
    ev('run.completed', { total_ms: 1200 }),
  ]
}

function setup(events: AskEvent[], mobile = false) {
  window.matchMedia = ((query: string) => ({
    matches: mobile && query.includes('max-width: 767px'),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
  const fetchMock = vi.fn((url: string) => {
    if (url === '/api/meta') return Promise.resolve(new Response(JSON.stringify(META)))
    if (url.startsWith('/api/chunks/')) {
      const id = decodeURIComponent(url.replace('/api/chunks/', ''))
      return Promise.resolve(
        new Response(JSON.stringify({ article_id: id, article_text: ARTICLES[id] ?? '無此條文' })),
      )
    }
    return Promise.resolve(sseResponse(events))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return fetchMock
}

async function finish() {
  const user = userEvent.setup()
  await user.type(screen.getByRole('textbox', { name: '你的問題' }), '紅燈右轉會被罰多少錢？')
  await user.click(screen.getByRole('button', { name: /提問/ }))
  await screen.findByRole('button', { name: '重新提問' })
  return user
}

const pressed = () => screen.getAllByRole('button', { pressed: true })

describe('citations, evidence and the full-text panel (desktop)', () => {
  it('makes the first citation active when the answer completes, with the panel closed', async () => {
    setup(run())
    await finish()
    expect(pressed()).toHaveLength(1)
    expect(pressed()[0]).toHaveTextContent('道交處罰條例 §53')
    expect(screen.queryByRole('region', { name: '條文全文' })).not.toBeInTheDocument()
    expect(screen.getByText('2 個引用皆已驗證')).toBeInTheDocument()
  })

  it('clicking a badge switches the active article without opening the panel', async () => {
    setup(run())
    const user = await finish()
    await user.click(screen.getByRole('button', { name: '道交處罰條例 §35' }))
    expect(pressed()).toHaveLength(1)
    expect(pressed()[0]).toHaveTextContent('§35')
    expect(screen.queryByRole('region', { name: '條文全文' })).not.toBeInTheDocument()
  })

  it('clicking a card opens the panel with the whole article, and switching articles keeps one active', async () => {
    const fetchMock = setup(run())
    const user = await finish()
    await user.click(screen.getByRole('button', { name: '查看道交處罰條例 第 53 條全文' }))
    const panel = await screen.findByRole('region', { name: '條文全文' })
    expect(await within(panel).findByText(/第五十三條全文/)).toBeInTheDocument()
    expect(within(panel).getByRole('heading', { name: '第 53 條' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/chunks/K0040012%3A53')

    // 面板開著時點另一個 badge：面板內容跟著切換，全頁仍只有一個 active
    await user.click(screen.getByRole('button', { name: '道交處罰條例 §35' }))
    expect(await within(panel).findByText(/第三十五條全文，整條/)).toBeInTheDocument()
    expect(pressed()).toHaveLength(1)
    expect(pressed()[0]).toHaveTextContent('§35')
  })

  it('opens an uncited article too, and labels it as retrieved', async () => {
    setup(run())
    const user = await finish()
    await user.click(screen.getByRole('button', { name: '查看道交處罰條例 第 58 條全文' }))
    const panel = await screen.findByRole('region', { name: '條文全文' })
    expect(within(panel).getByText('檢索到')).toBeInTheDocument()
    // 這一條沒有被引用，答案裡沒有對應的 badge，所以沒有任何 badge 被按下
    expect(screen.queryAllByRole('button', { pressed: true })).toHaveLength(0)
  })

  it('closes with Esc and returns focus to the element that opened it', async () => {
    setup(run())
    const user = await finish()
    const opener = screen.getByRole('button', { name: '查看道交處罰條例 第 35 條全文' })
    await user.click(opener)
    await screen.findByRole('region', { name: '條文全文' })
    await user.keyboard('{Escape}')
    await waitFor(() =>
      expect(screen.queryByRole('region', { name: '條文全文' })).not.toBeInTheDocument(),
    )
    expect(opener).toHaveFocus()
    expect(pressed()).toHaveLength(1) // 關閉面板後 active 不變
  })

  it('has external links that open in a new window with an accessible label', async () => {
    setup(run())
    await finish()
    const link = screen.getByRole('link', {
      name: '在全國法規資料庫查看道交處罰條例 第 53 條（另開新視窗）',
    })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('href', 'https://example.test/law')
  })

  it('works with the keyboard: a badge can be focused and activated with Enter', async () => {
    setup(run())
    const user = await finish()
    const badge = screen.getByRole('button', { name: '道交處罰條例 §35' })
    badge.focus()
    await user.keyboard('{Enter}')
    expect(badge).toHaveAttribute('aria-pressed', 'true')
  })

  it('merges chunks of one article into one card', async () => {
    setup(run())
    await finish()
    const evidence = screen.getByRole('complementary', { name: '依據' })
    expect(within(evidence).getAllByRole('heading', { level: 3 })).toHaveLength(3)
  })
})

describe('citation validation', () => {
  it('shows a dashed warning badge, a warning row and an explanation for an invalid citation', async () => {
    setup(run({ invalid: ['K0040012:77'] }))
    await finish()
    expect(screen.getByText(/有 1 個引用未通過驗證/)).toBeInTheDocument()
    const badge = screen.getByRole('button', { name: /§77/ })
    expect(badge).toHaveAccessibleDescription(/不在這次檢索到的條文中/)
    expect(badge).toHaveTextContent('⚠')
    expect(screen.queryByText(/皆已驗證/)).not.toBeInTheDocument()
  })
})

describe('mobile (< 768px)', () => {
  it('shows two tabs and moves the evidence to the second one', async () => {
    setup(run(), true)
    const user = await finish()
    expect(screen.getByRole('tab', { name: '答案', selected: true })).toBeInTheDocument()
    expect(screen.queryByRole('complementary', { name: '依據' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: '過程與依據' }))
    const evidence = screen.getByRole('complementary', { name: '依據' })
    expect(within(evidence).getByText('0.90')).toBeInTheDocument() // 分數
  })

  it('opens a drawer from a badge and steps through the retrieved articles', async () => {
    setup(run(), true)
    const user = await finish()
    await user.click(screen.getByRole('button', { name: '道交處罰條例 §53' }))
    const dialog = await screen.findByRole('dialog')
    expect(await within(dialog).findByText(/第五十三條全文/)).toBeInTheDocument()
    const prev = within(dialog).getByRole('button', { name: '← 上一則' })
    const next = within(dialog).getByRole('button', { name: '下一則 →' })
    expect(prev).toBeDisabled() // 第一則

    await user.click(next)
    expect(await within(dialog).findByText(/第三十五條全文/)).toBeInTheDocument()
    await user.click(next)
    expect(await within(dialog).findByText(/第五十八條全文/)).toBeInTheDocument()
    expect(next).toBeDisabled() // 最後一則

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('opens the drawer from an item in the evidence list', async () => {
    setup(run(), true)
    const user = await finish()
    await user.click(screen.getByRole('tab', { name: '過程與依據' }))
    await user.click(screen.getByRole('button', { name: /道交處罰條例 第 58 條/ }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })
})
