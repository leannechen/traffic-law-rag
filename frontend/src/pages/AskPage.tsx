import { useEffect } from 'react'
import { useAskContext } from '../features/ask/AskContext'
import { ResultView } from '../features/ask/ResultView'
import { HomeView } from './HomeView'

const SITE_NAME = '交通法規資料庫'

/** `/`：沒有 `?q=` 是首頁；有 `?q=` 是這一題的結果頁。 */
export function AskPage() {
  const { state, question, ask, stop, goHome } = useAskContext()

  useEffect(() => {
    document.title = question ? `${question}｜${SITE_NAME}` : SITE_NAME
    return () => {
      document.title = SITE_NAME
    }
  }, [question])

  if (!question) return <HomeView onAsk={ask} />
  // 網址剛變、提問還沒開始的那一瞬間：先以「進行中」的樣子顯示，避免閃一下空白
  const shown = state.phase === 'idle' ? { ...state, phase: 'streaming' as const, question } : state
  return <ResultView state={shown} onAsk={ask} onStop={stop} onReset={goHome} />
}
