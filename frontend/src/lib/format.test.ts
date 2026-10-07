import { formatDate } from './format'

describe('formatDate', () => {
  it('formats YYYYMMDD', () => {
    expect(formatDate('20260817')).toBe('2026-08-17')
  })

  it('leaves other formats alone', () => {
    expect(formatDate('2026-10-05')).toBe('2026-10-05')
    expect(formatDate('')).toBe('')
  })
})
