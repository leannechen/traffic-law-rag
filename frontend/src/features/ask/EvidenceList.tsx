import { formatDate } from '../../lib/format'
import type { ArticleEvidence } from './articles'
import styles from './EvidenceList.module.css'

type Props = {
  evidence: ArticleEvidence[]
  cited: string[]
  /** 串流中尚未有檢索結果時，先顯示骨架 */
  loading: boolean
}

/**
 * 依據（右欄）。此步卡片一律不可點（互動留到 Step 8）。
 * 串流中依檢索分數排序；完成時的「已引用在上」由呼叫端先排好。
 */
export function EvidenceList({ evidence, cited, loading }: Props) {
  const citedCount = evidence.filter((e) => cited.includes(e.articleId)).length
  return (
    <aside aria-label="依據" className={styles.root}>
      <div className={styles.head}>
        <h2 className={styles.title}>依據</h2>
        {evidence.length > 0 && (
          <span className={styles.count}>
            已引用 {citedCount} · 檢索到 {evidence.length}
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
        return (
          <article
            key={article.articleId}
            className={`${styles.card} ${isCited ? styles.cited : styles.uncited}`}
          >
            <div className={styles.cardHead}>
              <span className={isCited ? styles.tagCited : styles.tagUncited}>
                {isCited ? '已引用' : '檢索到'}
              </span>
              <h3 className={styles.cardTitle}>
                {article.lawShortName} 第 {article.articleNo} 條
              </h3>
            </div>
            <p className={styles.snippet}>{article.snippet}</p>
            {isCited && (
              <span className={styles.amended}>最新異動 {formatDate(article.amendedDate)}</span>
            )}
          </article>
        )
      })}
    </aside>
  )
}
