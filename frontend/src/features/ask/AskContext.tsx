import { createContext, type ReactNode, useContext } from 'react'
import { useAsk } from './useAsk'

type AskValue = ReturnType<typeof useAsk>

const AskContext = createContext<AskValue | null>(null)

/** 問答狀態放在路由之上：切到「關於」再回來，進行中的串流不會中斷。重新整理則回到首頁（spec 5.5-G8）。 */
export function AskProvider({ children }: { children: ReactNode }) {
  return <AskContext.Provider value={useAsk()}>{children}</AskContext.Provider>
}

export function useAskContext(): AskValue {
  const value = useContext(AskContext)
  if (!value) throw new Error('useAskContext must be used inside <AskProvider>')
  return value
}
