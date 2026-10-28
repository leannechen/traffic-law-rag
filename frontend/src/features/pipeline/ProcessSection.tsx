import { useMemo, useState } from 'react'
import { ChevronIcon } from '../../components/icons'
import type { ArticleEvidence } from '../ask/articles'
import type { AskState } from '../ask/askReducer'
import { PipelineSteps } from './PipelineSteps'
import styles from './ProcessSection.module.css'
import { RetrievalPanel } from './RetrievalPanel'
import { pipelineSteps } from './steps'

type Props = {
  state: AskState
  /** 以「條」為單位、依檢索名次排列的檢索結果 */
  articles: ArticleEvidence[]
}

/**
 * 檢索過程：PipelineSteps ＋ RetrievalPanel。
 * 預設展開，回答完成後也不自動收合（避免畫面跳動），可手動展開／收合成一行摘要。
 * 手機：直式列表。
 */
export function ProcessSection({ state, articles }: Props) {
  const { phase, totalMs, cited, queries, results, question } = state
  const [open, setOpen] = useState(true)
  const steps = useMemo(() => pipelineSteps(state), [state])

  // 沒有啟用改寫時，後端送出的查詢就是原問題：不當成「改寫查詢」顯示
  const rewritten = queries.length === 1 && queries[0] === question ? [] : queries
  const done = phase === 'done'
  const doneCount = steps.filter((s) => s.status === 'done').length
  const seconds = totalMs === null ? '' : ` · ${(totalMs / 1000).toFixed(1)} 秒`
  // 桌面的摘要多一段「檢索到 N 條」；手機版面窄，只留步驟數與耗時（畫板 MobileProcess）
  const summary = done ? (
    <>
      ✓ {doneCount} 個步驟完成
      <span className={styles.desktopOnly}> · 檢索到 {articles.length} 條</span>
      {seconds}
    </>
  ) : null

  return (
    <section aria-label="檢索過程" className={styles.root}>
      <button
        type="button"
        className={styles.toggle}
        aria-expanded={open}
        aria-controls="process-body"
        onClick={() => setOpen((o) => !o)}
      >
        <ChevronIcon size={16} className={open ? styles.open : ''} />
        <span className={styles.label}>檢索過程</span>
        <span className={styles.hint}>
          {summary}
          {done && <span className={styles.action}>　{open ? '收合' : '展開'}</span>}
        </span>
      </button>
      {open && (
        <div id="process-body" className={styles.body}>
          <PipelineSteps steps={steps} />
          <RetrievalPanel
            queries={rewritten}
            articles={articles}
            cited={cited}
            showCitation={done}
            loading={phase === 'streaming' && results.length === 0}
          />
        </div>
      )}
    </section>
  )
}
