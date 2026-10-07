import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import App from '../../App'
import { META } from '../../test-utils'
import type { EvalReport, EvalRow } from '../../types/eval'
import {
  articleLabel,
  citationCell,
  formatEvalDate,
  numbersCell,
  percent,
  retrievalCell,
} from './labels'

afterEach(() => vi.unstubAllGlobals())

const row = (overrides: Partial<EvalRow>): EvalRow => ({
  id: 'q01',
  question: '紅燈右轉會被罰多少錢？',
  category: 'fine_amount',
  should_refuse: false,
  expected: ['K0040012:53'],
  retrieved: [
    { article_id: 'K0040012:53', score: 0.91 },
    { article_id: 'K0040012:58', score: 0.6 },
  ],
  retrieval: 'hit',
  first_hit_rank: 1,
  citation: 'ok',
  numbers: 'ok',
  fact_amounts_expected: 2,
  fact_amounts_found: 2,
  ...overrides,
})

const REPORT: EvalReport = {
  name: 'test',
  evaluated_at: '2000-01-02T03:04:05+00:00',
  data_version: '2000-01-01',
  counts: { verified: 4, answerable: 3, out_of_scope: 1 },
  metrics: {
    recall_at_5: 1,
    mrr: 0.8452,
    citation_accuracy: 0.9,
    number_accuracy: null,
    refusal_accuracy: 1,
  },
  questions: [
    row({}),
    row({
      id: 'q07',
      question: '撞到人之後可以先把車移走嗎？',
      category: 'accident',
      retrieval: 'partial',
      first_hit_rank: 2,
      citation: 'wrong',
      numbers: 'mismatch',
    }),
    row({
      id: 'q09',
      question: '另一題',
      category: 'cross_law',
      retrieval: 'miss',
      first_hit_rank: null,
      numbers: 'na',
    }),
    row({
      id: 'q26',
      question: '今天天氣怎麼樣？',
      category: 'out_of_scope',
      should_refuse: true,
      expected: [],
      retrieved: [],
      retrieval: 'na',
      first_hit_rank: null,
      citation: 'refused_ok',
      numbers: 'na',
      fact_amounts_expected: null,
      fact_amounts_found: null,
    }),
  ],
}

function setup(report: EvalReport | 'missing', mobile = false) {
  window.matchMedia = ((query: string) => ({
    matches: mobile && query.includes('max-width: 767px'),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url === '/api/meta') return Promise.resolve(new Response(JSON.stringify(META)))
      return Promise.resolve(
        report === 'missing'
          ? new Response('{}', { status: 404 })
          : new Response(JSON.stringify(report)),
      )
    }),
  )
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/eval']}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('labels', () => {
  it('formats percentages without padding whole numbers', () => {
    expect(percent(1)).toBe('100%')
    expect(percent(0.8452)).toBe('84.5%')
    expect(percent(0.9)).toBe('90%')
  })

  it('maps states to a symbol, a word and a tone', () => {
    expect(retrievalCell('hit', 2)).toEqual({ symbol: '✓', text: '第 2 名', tone: 'ok' })
    expect(retrievalCell('partial', null).symbol).toBe('△')
    expect(citationCell('false_refusal').tone).toBe('err')
    expect(numbersCell('na').text).toBe('不適用')
  })

  it('shows an article with its law short name, or just the number when unknown', () => {
    expect(articleLabel('K0040012:53-1', { K0040012: '道交處罰條例' })).toBe('道交處罰條例 §53-1')
    expect(articleLabel('X:9', {})).toBe('§9')
  })

  it('shows only the date part of the evaluation time', () => {
    expect(formatEvalDate('2000-01-02T03:04:05+00:00')).toBe('2000-01-02')
  })
})

describe('評估頁', () => {
  it('shows the header facts and the five metrics from the report', async () => {
    setup(REPORT)
    expect(await screen.findByText('評估日期 2000-01-02')).toBeInTheDocument()
    expect(screen.getByText('資料版本 2000-01-01')).toBeInTheDocument()
    expect(screen.getByText('題數 4 題（範圍外 1 題）')).toBeInTheDocument()
    const metrics = screen.getByRole('region', { name: '指標' })
    expect(within(metrics).getByText('Recall@5')).toBeInTheDocument()
    expect(within(metrics).getAllByText('100%')).toHaveLength(2) // Recall、Refusal
    expect(within(metrics).getByText('0.85')).toBeInTheDocument()
    expect(within(metrics).getByText('90%')).toBeInTheDocument()
    expect(within(metrics).getByText('—')).toBeInTheDocument() // 數字正確率沒有資料
    expect(document.body).not.toHaveTextContent(/\[(XX|N|0\.XX|YYYY)/) // 不留畫板的佔位符
  })

  it('shows one row per question with retrieval, citation and numbers', async () => {
    setup(REPORT)
    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(4)
    expect(rows[0]).toHaveTextContent('q01紅燈右轉會被罰多少錢？罰鍰金額✓ 第 1 名✓ 正確✓ 一致')
    expect(rows[1]).toHaveTextContent('△ 部分命中')
    expect(rows[1]).toHaveTextContent('⨯ 有誤')
    expect(rows[1]).toHaveTextContent('⨯ 不一致')
    expect(rows[2]).toHaveTextContent('⨯ 未命中')
    expect(rows[3]).toHaveTextContent('範圍外')
    expect(rows[3]).toHaveTextContent('✓ 已拒答')
  })

  it('filters by category and shows the symbol legend', async () => {
    setup(REPORT)
    const user = userEvent.setup()
    await screen.findByRole('table')
    expect(screen.getByRole('button', { name: '全部', pressed: true })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '範圍外' }))
    expect(screen.getByRole('button', { name: '範圍外', pressed: true })).toBeInTheDocument()
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(2)
    expect(screen.getByText('1 / 4 題')).toBeInTheDocument()
    expect(screen.getByText(/符號說明/)).toBeInTheDocument()
  })

  it('expands a row to show the expected articles and the top five retrieved with scores', async () => {
    setup(REPORT)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: '展開 q01' }))
    expect(screen.getByRole('button', { name: '收合 q01' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(screen.getByText(/道交處罰條例 §53 · 重點金額 2 \/ 2/)).toBeInTheDocument()
    expect(
      screen.getByText('道交處罰條例 §53 (0.91) · 道交處罰條例 §58 (0.60)'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '收合 q01' }))
    expect(screen.queryByText(/系統檢索前 5 筆/)).not.toBeInTheDocument()
  })

  it('says an out-of-scope question should be refused', async () => {
    setup(REPORT)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: '展開 q26' }))
    expect(screen.getByText('範圍外：應該拒答')).toBeInTheDocument()
  })

  it('shows a message when no report is published', async () => {
    setup('missing')
    expect(await screen.findByRole('alert')).toHaveTextContent('目前沒有可顯示的評估結果')
  })

  it('uses cards on mobile and still expands a question', async () => {
    setup(REPORT, true)
    const user = userEvent.setup()
    await screen.findByText('評估日期 2000-01-02')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /q07/ }))
    expect(screen.getByText('系統檢索前 5 筆')).toBeInTheDocument()
  })
})
