import type { ReactNode } from 'react'
import styles from './AnswerStream.module.css'
import type { ArticleEvidence } from './articles'
import type { Segment } from './askReducer'

type Props = {
  segments: Segment[]
  evidence: ArticleEvidence[]
  /** 串流中：顯示游標 */
  streaming: boolean
  /** 已停止：文字轉淡，表示答案不完整 */
  stopped: boolean
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

function badgeLabel(articleId: string, evidence: ArticleEvidence[]): string {
  const found = evidence.find((e) => e.articleId === articleId)
  return found ? `${found.lawShortName} §${found.articleNo}` : articleId
}

/**
 * 答案文字。引用標記先以不可點的樣式顯示（互動留到 Step 8）。
 * 串流中與停止後都沒有任何可點擊的元素。
 */
export function AnswerStream({ segments, evidence, streaming, stopped }: Props) {
  return (
    <p className={`${styles.root} ${stopped ? styles.stopped : ''}`}>
      {segments.map((segment, i) =>
        segment.kind === 'text' ? (
          // biome-ignore lint/suspicious/noArrayIndexKey: 片段只會往後附加，位置就是身分
          <span key={i}>{renderBold(segment.text)}</span>
        ) : (
          // biome-ignore lint/suspicious/noArrayIndexKey: 同上
          <span key={i} className={styles.badge}>
            {badgeLabel(segment.articleId, evidence)}
          </span>
        ),
      )}
      {streaming && <span className={styles.cursor} aria-hidden="true" />}
    </p>
  )
}
