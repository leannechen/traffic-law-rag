import { type ReactNode, useId, useState } from 'react'
import styles from './AnswerStream.module.css'
import type { ArticleEvidence } from './articles'
import type { Segment } from './askReducer'

export type CitationSelection = {
  /** 完成後才可互動；串流中與停止後引用標記都不可點 */
  interactive: boolean
  activeId: string | null
  hoverId: string | null
  /** 驗證沒通過的引用（條 id） */
  invalidIds: ReadonlySet<string>
  onSelect: (articleId: string) => void
  onHover: (articleId: string | null) => void
}

type Props = {
  segments: Segment[]
  evidence: ArticleEvidence[]
  /** 串流中：顯示游標 */
  streaming: boolean
  /** 已停止：文字轉淡，表示答案不完整 */
  stopped: boolean
  selection: CitationSelection
}

function badgeLabel(articleId: string, evidence: ArticleEvidence[]): string {
  const found = evidence.find((e) => e.articleId === articleId)
  // 不在檢索結果裡的引用（驗證會判為無效）：不露出內部 id，只顯示條號
  return found
    ? `${found.lawShortName} §${found.articleNo}`
    : `§${articleId.split(':')[1] ?? articleId}`
}

/** 模型偶爾用 **粗體** 標小標；只處理這一種標記，其餘 Markdown 原樣顯示。 */
export function renderBold(text: string): ReactNode[] {
  return text.split(/(\*\*[^*\n]+\*\*)/).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? (
      // biome-ignore lint/suspicious/noArrayIndexKey: 片段順序固定
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : (
      part
    ),
  )
}

function InvalidBadge({ label }: { label: string }) {
  const tipId = useId()
  const [open, setOpen] = useState(false)
  return (
    <span className={styles.invalidWrap}>
      <button
        type="button"
        className={styles.invalid}
        aria-describedby={tipId}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setOpen(false)}
      >
        <span aria-hidden="true">⚠</span>
        {label}
        <span className="visually-hidden">（引用未通過驗證）</span>
      </button>
      <span id={tipId} role="tooltip" className={`${styles.tip} ${open ? styles.tipOpen : ''}`}>
        <strong>此引用未通過驗證</strong>「{label}
        」不在這次檢索到的條文中，系統無法確認它支持這句話。請以條文原文為準。
      </span>
    </span>
  )
}

/**
 * 答案文字與引用標記。串流中與停止後標記是不可點的 span；完成後才是按鈕。
 * 驗證沒通過的引用用虛線框加圖示（不只靠顏色），並附說明。
 */
export function AnswerStream({ segments, evidence, streaming, stopped, selection }: Props) {
  const { interactive, activeId, hoverId, invalidIds, onSelect, onHover } = selection
  return (
    <p className={`${styles.root} ${stopped ? styles.stopped : ''}`}>
      {segments.map((segment, i) => {
        if (segment.kind === 'text') {
          // biome-ignore lint/suspicious/noArrayIndexKey: 片段只會往後附加，位置就是身分
          return <span key={i}>{renderBold(segment.text)}</span>
        }
        const id = segment.articleId
        const label = badgeLabel(id, evidence)
        if (!interactive) {
          return (
            // biome-ignore lint/suspicious/noArrayIndexKey: 同上
            <span key={i} className={styles.badge}>
              {label}
            </span>
          )
        }
        if (invalidIds.has(id) || !evidence.some((e) => e.articleId === id)) {
          // biome-ignore lint/suspicious/noArrayIndexKey: 同上
          return <InvalidBadge key={i} label={label} />
        }
        const active = id === activeId
        const hover = id === hoverId && !active
        return (
          <button
            // biome-ignore lint/suspicious/noArrayIndexKey: 同上
            key={i}
            type="button"
            aria-pressed={active}
            className={`${styles.badge} ${styles.button} ${active ? styles.active : ''} ${hover ? styles.hover : ''}`}
            onClick={() => onSelect(id)}
            onMouseEnter={() => onHover(id)}
            onMouseLeave={() => onHover(null)}
            onFocus={() => onHover(id)}
            onBlur={() => onHover(null)}
          >
            {label}
          </button>
        )
      })}
      {streaming && <span className={styles.cursor} aria-hidden="true" />}
    </p>
  )
}
