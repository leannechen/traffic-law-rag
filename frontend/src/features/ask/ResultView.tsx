import { useEffect, useMemo, useRef } from 'react'
import { SpinnerIcon, StopIcon } from '../../components/icons'
import { PageShell } from '../../components/PageShell'
import { useMeta } from '../../lib/useMeta'
import { AnswerStream } from './AnswerStream'
import { groupArticles, sortForDone } from './articles'
import type { AskState } from './askReducer'
import { ErrorNotice } from './ErrorNotice'
import { EvidenceList } from './EvidenceList'
import { ProcessSection } from './ProcessSection'
import { RefusalNotice } from './RefusalNotice'
import styles from './ResultView.module.css'
import { ScopeAside } from './ScopeAside'

type Props = {
  state: AskState
  onAsk: (question: string) => void
  onStop: () => void
  onReset: () => void
}

const STATUS_TEXT: Record<AskState['phase'], string> = {
  idle: '',
  streaming: '正在產生答案',
  done: '答案已完成',
  refused: '查無依據，因此不作答',
  stopped: '已停止產生，答案不完整',
  error: '發生錯誤',
}

/** 問答結果頁。左欄固定順序：你的問題 → 檢索過程 → 答案；右欄是依據（5.5-A）。 */
export function ResultView({ state, onAsk, onStop, onReset }: Props) {
  const { phase, question, segments, results, cited, refusal, validation, totalMs, error } = state
  const { data: meta } = useMeta()
  const titleRef = useRef<HTMLHeadingElement>(null)

  // 從首頁切到結果頁：被卸載的輸入框／範例按鈕原本有焦點，把焦點與捲動位置帶到「你的問題」
  useEffect(() => {
    window.scrollTo(0, 0)
    titleRef.current?.focus()
  }, [])

  const evidence = useMemo(() => {
    const grouped = groupArticles(results)
    return phase === 'done' ? sortForDone(grouped, cited) : grouped
  }, [results, cited, phase])

  const streaming = phase === 'streaming'
  const refused = phase === 'refused' && refusal !== null

  return (
    <PageShell>
      <div className={styles.grid}>
        <div className={styles.main}>
          <section aria-label="你的問題" className={styles.question}>
            <p className={styles.kicker}>你的問題</p>
            <h1 ref={titleRef} tabIndex={-1} className={styles.title}>
              {question}
            </h1>
            {streaming && (
              <div className={styles.status}>
                <span className={styles.working} role="status">
                  <SpinnerIcon size={16} className={styles.spinner} />
                  正在產生答案…
                </span>
                <button type="button" className={styles.stop} onClick={onStop}>
                  <StopIcon />
                  停止
                </button>
              </div>
            )}
          </section>

          {!streaming && (
            // 只播報階段變化一次；逐字出現的答案本身不設 aria-live，避免每個 delta 都被念出來
            <p className="visually-hidden" role="status">
              {STATUS_TEXT[phase]}
            </p>
          )}

          {refused ? (
            <RefusalNotice refusal={refusal} onAsk={onAsk} onNewQuestion={onReset} />
          ) : (
            <>
              {phase !== 'error' && <ProcessSection state={state} articleCount={evidence.length} />}
              <section aria-label="答案" className={styles.answer}>
                <h2 className={styles.answerTitle}>答案</h2>
                {segments.length === 0 && streaming && (
                  <p className={styles.waiting}>等待第一段回答…</p>
                )}
                {segments.length > 0 && (
                  <AnswerStream
                    segments={segments}
                    evidence={evidence}
                    streaming={streaming}
                    stopped={phase === 'stopped'}
                  />
                )}
                {phase === 'stopped' && (
                  <div className={styles.stopped}>
                    <span className={styles.stoppedText}>
                      <StopIcon />
                      你已停止產生，答案不完整
                    </span>
                    <button
                      type="button"
                      className={styles.secondary}
                      onClick={() => onAsk(question)}
                    >
                      重新產生
                    </button>
                  </div>
                )}
                {phase === 'error' && error && (
                  <ErrorNotice
                    error={error}
                    runId={state.runId}
                    onRetry={() => onAsk(question)}
                    onHome={onReset}
                  />
                )}
                {phase === 'done' && (
                  <div className={styles.info}>
                    {validation && validation.invalid.length > 0 ? (
                      <p className={styles.warn}>
                        有 {validation.invalid.length} 個引用未通過驗證，請以條文原文為準。
                      </p>
                    ) : (
                      validation && (
                        <p className={styles.ok}>
                          ✓ 引用驗證：{validation.valid.length} /{' '}
                          {validation.valid.length + validation.invalid.length} 通過
                        </p>
                      )
                    )}
                    <p className={styles.meta}>
                      {meta && `資料版本 ${meta.data_version}`}
                      {totalMs !== null && ` · 耗時 ${(totalMs / 1000).toFixed(1)} 秒`}
                    </p>
                    <button type="button" className={styles.secondary} onClick={onReset}>
                      重新提問
                    </button>
                  </div>
                )}
              </section>
            </>
          )}
        </div>

        {refused ? (
          <ScopeAside />
        ) : (
          phase !== 'error' && (
            <EvidenceList evidence={evidence} cited={cited} loading={streaming} />
          )
        )}
      </div>
    </PageShell>
  )
}
