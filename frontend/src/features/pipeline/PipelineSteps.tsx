import styles from './PipelineSteps.module.css'
import { formatDuration, type PipelineStep, type StepStatus } from './steps'

const SYMBOL: Record<StepStatus, string> = {
  done: '✓',
  running: '◐',
  waiting: '○',
  skipped: '—',
  insufficient: '⨯',
  stopped: '◐',
}

// 狀態不能只靠顏色：符號之外，螢幕閱讀器也會聽到狀態文字
const STATUS_TEXT: Record<StepStatus, string> = {
  done: '完成',
  running: '進行中',
  waiting: '等待中',
  skipped: '略過',
  insufficient: '停在這一步',
  stopped: '已停止',
}

type Props = {
  steps: PipelineStep[]
  /** full：每步有摘要與耗時（問答結果頁）；compact：只有符號與步驟名（拒答頁的「為什麼不回答」） */
  variant?: 'full' | 'compact'
}

/** 流程圖的簡化替代版：五個步驟，桌面橫排、手機直式列表。 */
export function PipelineSteps({ steps, variant = 'full' }: Props) {
  return (
    <ol
      aria-label="處理步驟"
      className={`${styles.root} ${variant === 'compact' ? styles.compact : styles.full}`}
    >
      {steps.map((step) => (
        <li key={step.id} className={`${styles.step} ${styles[step.status]}`}>
          <span className={styles.bar} aria-hidden="true" />
          <span className={styles.head}>
            <span aria-hidden="true" className={step.status === 'running' ? styles.spin : ''}>
              {SYMBOL[step.status]}
            </span>
            {step.label}
            {variant === 'compact' && step.status === 'skipped' && '（略過）'}
            <span className="visually-hidden">（{STATUS_TEXT[step.status]}）</span>
          </span>
          {variant === 'full' && <span className={styles.detail}>{step.detail}</span>}
          {variant === 'compact' && step.status === 'insufficient' && (
            <span className={styles.detail}>停在這一步</span>
          )}
          {variant === 'full' && (
            <span className={styles.time}>
              {step.status === 'running' ? '…' : formatDuration(step.durationMs)}
            </span>
          )}
        </li>
      ))}
    </ol>
  )
}
