import type { ReactNode } from 'react'
import { CheckIcon, ChevronIcon, SpinnerIcon } from '../../components/icons'
import type { AskState } from './askReducer'
import styles from './ProcessSection.module.css'

const STEP_LABELS = {
  rewrite: '改寫問題',
  retrieve: '檢索條文',
  rerank: '重排序',
  gate: '相關度檢查',
  generate: '產生答案',
  validate: '驗證引用',
} as const

type Props = { state: AskState; articleCount: number }

/**
 * 檢索過程：此步只顯示目前進行到哪一步。
 * 完整的 PipelineSteps 與 RetrievalPanel 在 Step 9。
 */
export function ProcessSection({ state, articleCount }: Props) {
  const { phase, currentStep, steps, totalMs } = state
  const doneCount = Object.values(steps).filter((s) => s?.status === 'done').length
  const streaming = phase === 'streaming'

  let body: ReactNode
  if (streaming) {
    body = (
      <p className={styles.current} role="status">
        <SpinnerIcon size={16} className={styles.spinner} />
        {currentStep ? `${STEP_LABELS[currentStep]}…` : '準備中…'}
      </p>
    )
  } else if (phase === 'done') {
    const seconds = totalMs === null ? '' : ` · ${(totalMs / 1000).toFixed(1)} 秒`
    body = (
      <p className={styles.summary}>
        <CheckIcon size={16} strokeWidth={2.4} />
        {doneCount} 個步驟完成 · 檢索到 {articleCount} 條{seconds}
      </p>
    )
  } else {
    body = (
      <p className={styles.summary}>
        {currentStep || doneCount > 0 ? `停在：${lastStepLabel(state)}` : '尚未開始檢索'}
      </p>
    )
  }

  return (
    <section aria-label="檢索過程" className={styles.root}>
      <h2 className={styles.title}>
        <ChevronIcon size={16} className={streaming ? styles.open : ''} />
        檢索過程
        {streaming && <span className={styles.hint}>完成後自動收合</span>}
      </h2>
      {body}
    </section>
  )
}

function lastStepLabel(state: AskState): string {
  const order = ['rewrite', 'retrieve', 'rerank', 'gate', 'generate', 'validate'] as const
  const reached = order.filter((name) => state.steps[name])
  const last = reached[reached.length - 1]
  return last ? STEP_LABELS[last] : '尚未開始檢索'
}
