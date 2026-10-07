import { useCallback, useEffect, useReducer, useRef } from 'react'
import { AskHttpError, streamAsk } from '../../lib/sse'
import { type AskError, askReducer, initialAskState } from './askReducer'

const DEFAULT_RETRY_SECONDS = 60

/** 把送出請求或讀取串流時的例外轉成畫面要顯示的錯誤。 */
export function toAskError(e: unknown, receivedAny: boolean): AskError {
  if (e instanceof AskHttpError) {
    if (e.status === 429) {
      return { code: 'rate_limited', retryAfter: e.retryAfter ?? DEFAULT_RETRY_SECONDS }
    }
    if (e.status === 422) return { code: 'invalid_question', message: e.detail }
    return { code: 'http_error', message: e.detail || `HTTP ${e.status}`, status: e.status }
  }
  return { code: receivedAny ? 'stream_interrupted' : 'network_error' }
}

export function useAsk() {
  const [state, dispatch] = useReducer(askReducer, initialAskState)
  const controllerRef = useRef<AbortController | null>(null)

  const abort = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
  }, [])

  const start = useCallback(
    async (question: string) => {
      abort()
      const controller = new AbortController()
      controllerRef.current = controller
      dispatch({ type: 'submit', question })
      let receivedAny = false
      try {
        for await (const event of streamAsk(question, controller.signal)) {
          if (controller.signal.aborted) return
          receivedAny = true
          dispatch({ type: 'event', event })
        }
        if (!controller.signal.aborted) dispatch({ type: 'stream.ended' })
      } catch (e) {
        if (controller.signal.aborted) return
        dispatch({ type: 'failed', error: toAskError(e, receivedAny) })
      }
    },
    [abort],
  )

  const stop = useCallback(() => {
    abort()
    dispatch({ type: 'stop' })
  }, [abort])

  const reset = useCallback(() => {
    abort()
    dispatch({ type: 'reset' })
  }, [abort])

  useEffect(() => abort, [abort])

  return { state, start, stop, reset }
}
