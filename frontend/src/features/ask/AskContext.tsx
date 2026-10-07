import { createContext, type ReactNode, useCallback, useContext, useEffect } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useAsk } from './useAsk'

type AskValue = {
  state: ReturnType<typeof useAsk>['state']
  /** 網址上的問題（`/?q=…`）；沒有就是首頁 */
  question: string
  /** 提問：把問題放進網址（新增一筆瀏覽紀錄）。問的是目前這一題時，視為重試，不改網址。 */
  ask: (question: string) => void
  stop: () => void
  /** 回到首頁（`/`） */
  goHome: () => void
}

const AskContext = createContext<AskValue | null>(null)

export function questionPath(question: string): string {
  return `/?q=${encodeURIComponent(question)}`
}

/**
 * 問答狀態放在路由之上：切到「關於」再回來，進行中的串流不會中斷。
 * 網址是問題的唯一來源：`/?q=…` 就是在問那一題，`/` 就是首頁。
 * 因此上一頁／下一頁、重新整理、分享連結都會回到對應的問題（重新整理與分享會重新提問）。
 */
export function AskProvider({ children }: { children: ReactNode }) {
  const { state, start, stop, reset } = useAsk()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [params] = useSearchParams()
  const question = params.get('q')?.trim() ?? ''

  // 網址決定該顯示什麼：在 `/` 時，有問題就（重新）提問，沒有就回到首頁空狀態
  useEffect(() => {
    if (pathname !== '/') return // 看其他頁面時，保留進行中的問答
    if (!question) {
      if (state.phase !== 'idle') reset()
    } else if (state.phase === 'idle' || state.question !== question) {
      void start(question)
    }
  }, [pathname, question, state.phase, state.question, start, reset])

  const ask = useCallback(
    (next: string) => {
      if (pathname === '/' && next === question) void start(next)
      else navigate(questionPath(next))
    },
    [pathname, question, start, navigate],
  )

  const goHome = useCallback(() => navigate('/'), [navigate])

  return (
    <AskContext.Provider value={{ state, question, ask, stop, goHome }}>
      {children}
    </AskContext.Provider>
  )
}

export function useAskContext(): AskValue {
  const value = useContext(AskContext)
  if (!value) throw new Error('useAskContext must be used inside <AskProvider>')
  return value
}
