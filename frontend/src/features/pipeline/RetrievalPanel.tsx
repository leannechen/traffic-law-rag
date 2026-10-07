import type { ArticleEvidence } from '../ask/articles'
import styles from './RetrievalPanel.module.css'

type Props = {
  /** 改寫後的查詢（沒有啟用改寫時是空陣列） */
  queries: string[]
  /** 以「條」為單位，依檢索名次排列 */
  articles: ArticleEvidence[]
  cited: string[]
  /** 完成後才標示已引用／未引用 */
  showCitation: boolean
  loading: boolean
}

/** 檢索結果：名次、法規與條號、分數條與分數。 */
export function RetrievalPanel({ queries, articles, cited, showCitation, loading }: Props) {
  return (
    <div className={styles.root}>
      <div className={styles.head}>
        <h3 className={styles.title}>檢索結果</h3>
        {queries.length > 0 && (
          <span className={styles.queries}>
            改寫查詢：{queries.map((q) => `「${q}」`).join('')}
          </span>
        )}
      </div>
      {loading && articles.length === 0 && (
        <div aria-hidden="true">
          {[70, 50].map((width) => (
            <div key={width} className={`${styles.row} ${styles.skeletonRow}`}>
              <span className={styles.skeleton} />
              <span className={styles.skeleton} style={{ width: `${width}%` }} />
              <span className={styles.skeletonBar} />
            </div>
          ))}
        </div>
      )}
      {!loading && articles.length === 0 && (
        <p className={styles.empty}>沒有找到相似度足夠的條文。</p>
      )}
      {articles.length > 0 && (
        <ol className={styles.list}>
          {articles.map((article, index) => {
            const isCited = cited.includes(article.articleId)
            return (
              <li key={article.articleId} className={styles.row}>
                <span className={styles.rank}>{String(index + 1).padStart(2, '0')}</span>
                <span className={styles.name}>
                  {article.lawShortName} §{article.articleNo}
                </span>
                {showCitation && (
                  <span className={isCited ? styles.tagCited : styles.tag}>
                    {isCited ? '已引用' : '未引用'}
                  </span>
                )}
                <span className={styles.score}>
                  <span className={styles.track} aria-hidden="true">
                    <span
                      className={showCitation && !isCited ? styles.fillPlain : styles.fill}
                      style={{ width: `${Math.round(article.score * 100)}%` }}
                    />
                  </span>
                  <span className={styles.value}>{article.score.toFixed(2)}</span>
                </span>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}
