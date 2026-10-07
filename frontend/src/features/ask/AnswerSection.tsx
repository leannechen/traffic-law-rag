import { StopIcon } from '../../components/icons'
import styles from './AnswerSection.module.css'
import { AnswerStream, type CitationSelection } from './AnswerStream'
import type { ArticleEvidence } from './articles'
import type { AskState } from './askReducer'
import { ErrorNotice } from './ErrorNotice'

type Props = {
  state: AskState
  evidence: ArticleEvidence[]
  selection: CitationSelection
  dataVersion: string | undefined
  onAsk: (question: string) => void
  onReset: () => void
}

/** 答案區塊：答案文字、已停止／錯誤提示、完成後的資訊列（引用驗證、資料版本、耗時）。 */
export function AnswerSection({ state, evidence, selection, dataVersion, onAsk, onReset }: Props) {
  const { phase, question, segments, cited, validation, totalMs, error } = state
  const streaming = phase === 'streaming'
  const invalidCount = validation?.invalid.length ?? 0

  return (
    <section aria-label="答案" className={styles.root}>
      <h2 className={styles.title}>答案</h2>
      {phase === 'done' && invalidCount > 0 && (
        <p className={styles.warnRow}>
          <span aria-hidden="true">⚠</span>有 {invalidCount} 個引用未通過驗證，請以條文原文為準。
        </p>
      )}
      {segments.length === 0 && streaming && <p className={styles.waiting}>等待第一段回答…</p>}
      {segments.length > 0 && (
        <AnswerStream
          segments={segments}
          evidence={evidence}
          streaming={streaming}
          stopped={phase === 'stopped'}
          selection={selection}
        />
      )}
      {phase === 'stopped' && (
        <div className={styles.stopped}>
          <span className={styles.stoppedText}>
            <StopIcon />
            你已停止產生，答案不完整
          </span>
          <button type="button" className={styles.secondary} onClick={() => onAsk(question)}>
            重新產生
          </button>
        </div>
      )}
      {phase === 'error' && error && (
        <ErrorNotice error={error} runId={state.runId} onRetry={() => onAsk(question)} />
      )}
      {phase === 'done' && (
        <div className={styles.info}>
          {validation && invalidCount === 0 && (
            <p className={styles.ok}>
              <span aria-hidden="true">✓</span>
              {cited.length} 個引用皆已驗證
            </p>
          )}
          {validation && invalidCount > 0 && (
            <p className={styles.warn}>
              {validation.valid.length} / {validation.valid.length + invalidCount} 個引用通過驗證
            </p>
          )}
          <p className={styles.meta}>
            {dataVersion && <span>資料版本 {dataVersion}</span>}
            {totalMs !== null && <span>耗時 {(totalMs / 1000).toFixed(1)} 秒</span>}
          </p>
          <button type="button" className={styles.again} onClick={onReset}>
            重新提問
          </button>
        </div>
      )}
    </section>
  )
}
