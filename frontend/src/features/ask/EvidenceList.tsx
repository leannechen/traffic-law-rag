import { formatDate } from '../../lib/format'
import type { ArticleEvidence } from './articles'
import styles from './EvidenceList.module.css'

export type EvidenceSelection = {
  /** 完成後才可互動；串流中與停止後卡片不可點（沒有連結、沒有 active 外框） */
  interactive: boolean
  activeId: string | null
  hoverId: string | null
  /** 點卡片標題或「查看全文」：設為 active 並開啟全文 */
  onOpen: (articleId: string) => void
  onHover: (articleId: string | null) => void
}

type Props = {
  evidence: ArticleEvidence[]
  cited: string[]
  /** 串流中尚未有檢索結果時，先顯示骨架 */
  loading: boolean
  selection: EvidenceSelection
  /** 手機的依據列表：整列可點，已引用顯示分數與兩行摘要，未引用只有標題與分數 */
  compact?: boolean
  /** 桌面全文面板開啟中：依據欄的可視高度要扣掉面板 */
  panelOpen?: boolean
}

function ScoreBar({ score, cited }: { score: number; cited: boolean }) {
  return (
    <span className={styles.scoreBar} aria-hidden="true">
      <span className={styles.track}>
        <span
          className={cited ? styles.fillCited : styles.fill}
          style={{ width: `${Math.round(score * 100)}%` }}
        />
      </span>
    </span>
  )
}

/**
 * 依據。串流中依檢索分數排序；完成時的「已引用在上」由呼叫端先排好。
 * 條文全文不在卡片裡展開：卡片只放摘要（以行數截斷）。
 */
export function EvidenceList({
  evidence,
  cited,
  loading,
  selection,
  compact = false,
  panelOpen = false,
}: Props) {
  const { interactive, activeId, hoverId, onOpen, onHover } = selection
  const citedCount = evidence.filter((e) => cited.includes(e.articleId)).length
  return (
    <aside
      aria-label="依據"
      className={`${styles.root} ${compact ? '' : styles.sticky} ${panelOpen ? styles.withPanel : ''}`}
    >
      <div className={styles.head}>
        <h2 className={styles.title}>依據</h2>
        {evidence.length > 0 && (
          <span className={styles.count}>
            已引用 {citedCount} · 檢索到 {evidence.length}
            {compact && ' · 依相似度排序'}
          </span>
        )}
      </div>
      {loading && evidence.length === 0 && (
        <div className={styles.skeletons} aria-hidden="true">
          <div className={styles.skeleton} />
          <div className={styles.skeleton} />
          <div className={styles.skeleton} />
        </div>
      )}
      {evidence.map((article) => {
        const isCited = cited.includes(article.articleId)
        const title = `${article.lawShortName} 第 ${article.articleNo} 條`
        const active = interactive && article.articleId === activeId
        const hover = interactive && isCited && article.articleId === hoverId && !active
        const className = [
          styles.card,
          isCited ? styles.cited : styles.uncited,
          active ? styles.activeCard : '',
          hover ? styles.hoverCard : '',
        ].join(' ')
        const tag = (
          <span className={isCited ? styles.tagCited : styles.tagUncited}>
            {isCited ? '已引用' : '檢索到'}
          </span>
        )

        if (compact) {
          const Wrapper = interactive ? 'button' : 'div'
          return (
            <article key={article.articleId} id={`card-${article.articleId}`} className={className}>
              <Wrapper
                {...(interactive
                  ? { type: 'button' as const, onClick: () => onOpen(article.articleId) }
                  : {})}
                className={styles.row}
              >
                <span className={styles.cardHead}>
                  {tag}
                  <h3 className={styles.cardTitle}>{title}</h3>
                  <span className={styles.score}>{article.score.toFixed(2)}</span>
                </span>
                <ScoreBar score={article.score} cited={isCited} />
                {isCited && <span className={styles.snippetTwo}>{article.snippet}</span>}
              </Wrapper>
            </article>
          )
        }

        return (
          <article
            key={article.articleId}
            id={`card-${article.articleId}`}
            className={className}
            onMouseEnter={interactive ? () => onHover(article.articleId) : undefined}
            onMouseLeave={interactive ? () => onHover(null) : undefined}
          >
            <div className={styles.cardHead}>
              {tag}
              <h3 className={styles.cardTitle}>
                {interactive ? (
                  <button
                    type="button"
                    className={styles.titleButton}
                    onClick={() => onOpen(article.articleId)}
                    onFocus={() => onHover(article.articleId)}
                    onBlur={() => onHover(null)}
                  >
                    {title}
                  </button>
                ) : (
                  title
                )}
              </h3>
            </div>
            <p className={styles.snippet}>{article.snippet}</p>
            {interactive ? (
              <div className={styles.foot}>
                <span className={styles.amended}>最新異動 {formatDate(article.amendedDate)}</span>
                <span className={styles.links}>
                  <button
                    type="button"
                    className={styles.openButton}
                    aria-label={`查看${title}全文`}
                    onClick={() => onOpen(article.articleId)}
                  >
                    查看全文
                  </button>
                  <a
                    href={article.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`在全國法規資料庫查看${title}（另開新視窗）`}
                  >
                    在全國法規資料庫查看 ↗
                  </a>
                </span>
              </div>
            ) : (
              isCited && (
                <span className={styles.amended}>最新異動 {formatDate(article.amendedDate)}</span>
              )
            )}
          </article>
        )
      })}
    </aside>
  )
}
