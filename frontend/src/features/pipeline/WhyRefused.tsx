import type { AskState } from '../ask/askReducer'
import { PipelineSteps } from './PipelineSteps'
import { pipelineSteps } from './steps'
import styles from './WhyRefused.module.css'

/**
 * 拒答頁的「為什麼不回答」：PipelineSteps 的拒答分支（停在哪一步、後面略過）
 * ＋ 最高相似度與門檻的對照條。
 */
export function WhyRefused({ state }: { state: AskState }) {
  const { refusal } = state
  if (!refusal) return null
  const { topScore, threshold, reason } = refusal
  const passed = topScore !== null && topScore >= threshold
  const pct = (value: number) => `${Math.max(0, Math.min(1, value)) * 100}%`

  return (
    <section aria-label="檢索過程" className={styles.root}>
      <h2 className={styles.title}>為什麼不回答</h2>
      <PipelineSteps steps={pipelineSteps(state)} variant="compact" />
      {topScore !== null && (
        <div className={styles.compare}>
          <div className={styles.line}>
            <span className={styles.strong}>最高相似度</span>
            <span className={styles.mono}>
              {topScore.toFixed(2)} {passed ? '≥' : '＜'} 門檻 {threshold.toFixed(2)}
            </span>
          </div>
          <div
            className={styles.track}
            role="img"
            aria-label={`最高相似度 ${topScore.toFixed(2)}，門檻 ${threshold.toFixed(2)}`}
          >
            <span
              className={passed ? styles.fillPassed : styles.fill}
              style={{ width: pct(topScore) }}
            />
            <span className={styles.marker} style={{ left: pct(threshold) }} />
          </div>
          <div className={styles.scale} aria-hidden="true">
            <span>0</span>
            <span>門檻</span>
            <span>1.0</span>
          </div>
          {reason === 'out_of_scope' && (
            <p className={styles.note}>
              相似度通過了門檻，但模型判斷這些條文不足以回答這個問題，所以沒有作答。
            </p>
          )}
        </div>
      )}
    </section>
  )
}
