import { act, renderHook } from '@testing-library/react'
import { AskHttpError } from '../../lib/sse'
import { toAskError } from './useAsk'
import { formatCountdown, useCountdown } from './useCountdown'

describe('formatCountdown', () => {
  it('formats seconds as mm:ss', () => {
    expect(formatCountdown(42)).toBe('00:42')
    expect(formatCountdown(61)).toBe('01:01')
    expect(formatCountdown(0)).toBe('00:00')
  })
})

describe('useCountdown', () => {
  afterEach(() => vi.useRealTimers())

  it('counts down to zero', () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useCountdown(3))
    expect(result.current).toBe(3)
    act(() => vi.advanceTimersByTime(1100))
    expect(result.current).toBe(2)
    act(() => vi.advanceTimersByTime(5000))
    expect(result.current).toBe(0)
  })
})

describe('toAskError', () => {
  it('maps 429 to rate_limited with the Retry-After value', () => {
    expect(toAskError(new AskHttpError(429, '', 42), false)).toEqual({
      code: 'rate_limited',
      retryAfter: 42,
    })
  })

  it('falls back to 60 seconds when Retry-After is missing', () => {
    expect(toAskError(new AskHttpError(429, '', null), false)).toMatchObject({ retryAfter: 60 })
  })

  it('distinguishes a network failure before and after the stream began', () => {
    expect(toAskError(new TypeError('network'), false).code).toBe('network_error')
    expect(toAskError(new TypeError('network'), true).code).toBe('stream_interrupted')
  })
})
