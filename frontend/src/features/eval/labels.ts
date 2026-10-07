import type { Citation, Numbers, Retrieval } from '../../types/eval'

export const CATEGORY_LABELS: Record<string, string> = {
  fine_amount: '罰鍰金額',
  definition: '行為定義',
  accident: '事故處理',
  cross_law: '跨法規',
  colloquial: '口語問法',
  out_of_scope: '範圍外',
}

export const CATEGORY_ORDER = Object.keys(CATEGORY_LABELS)

export type Tone = 'ok' | 'warn' | 'err' | 'na'
export type Cell = { symbol: string; text: string; tone: Tone }

export function retrievalCell(kind: Retrieval, rank: number | null): Cell {
  switch (kind) {
    case 'hit':
      return { symbol: '✓', text: rank ? `第 ${rank} 名` : '命中', tone: 'ok' }
    case 'partial':
      return { symbol: '△', text: '部分命中', tone: 'warn' }
    case 'miss':
      return { symbol: '⨯', text: '未命中', tone: 'err' }
    case 'na':
      return { symbol: '—', text: '不適用', tone: 'na' }
  }
}

export function citationCell(kind: Citation): Cell {
  switch (kind) {
    case 'ok':
      return { symbol: '✓', text: '正確', tone: 'ok' }
    case 'wrong':
      return { symbol: '⨯', text: '有誤', tone: 'err' }
    case 'refused_ok':
      return { symbol: '✓', text: '已拒答', tone: 'ok' }
    case 'answered_out_of_scope':
      return { symbol: '⨯', text: '不該作答', tone: 'err' }
    case 'false_refusal':
      return { symbol: '⨯', text: '誤拒', tone: 'err' }
  }
}

export function numbersCell(kind: Numbers): Cell {
  switch (kind) {
    case 'ok':
      return { symbol: '✓', text: '一致', tone: 'ok' }
    case 'mismatch':
      return { symbol: '⨯', text: '不一致', tone: 'err' }
    case 'na':
      return { symbol: '—', text: '不適用', tone: 'na' }
  }
}

/** 0.8452 → "84.5%"；0.1 → "10%"。整數百分比不補小數。 */
export function percent(value: number): string {
  const p = Math.round(value * 1000) / 10
  return `${Number.isInteger(p) ? p.toFixed(0) : p.toFixed(1)}%`
}

export function formatEvalDate(iso: string): string {
  return iso.slice(0, 10)
}

/** K0040012:53-1 → 53-1（條號）；找不到法規簡稱就只顯示條號。 */
export function articleLabel(articleId: string, shortNames: Record<string, string>): string {
  const [pcode, no = articleId] = articleId.split(':')
  const name = shortNames[pcode]
  return name ? `${name} §${no}` : `§${no}`
}
