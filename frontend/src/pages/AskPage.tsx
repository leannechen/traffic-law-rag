import { useAskContext } from '../features/ask/AskContext'
import { ResultView } from '../features/ask/ResultView'
import { HomeView } from './HomeView'

/** `/`：沒有提問時是首頁，提問後是結果頁（問答狀態只存在記憶體）。 */
export function AskPage() {
  const { state, start, stop, reset } = useAskContext()
  if (state.phase === 'idle') return <HomeView onAsk={start} />
  return <ResultView state={state} onAsk={start} onStop={stop} onReset={reset} />
}
