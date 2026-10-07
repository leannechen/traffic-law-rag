import styles from './ArticleBody.module.css'
import { useArticle } from './useArticle'

/** 條文全文（面板與抽屜共用）。一律顯示整條，各項樣式一致。 */
export function ArticleBody({ articleId, sourceUrl }: { articleId: string; sourceUrl: string }) {
  const { data, isPending, isError } = useArticle(articleId)
  if (isPending) return <p className={styles.state}>條文載入中…</p>
  if (isError) {
    return (
      <p className={styles.state} role="alert">
        暫時無法取得條文全文，請到{' '}
        <a href={sourceUrl} target="_blank" rel="noreferrer">
          全國法規資料庫
        </a>{' '}
        查看。
      </p>
    )
  }
  return <p className={styles.text}>{data.article_text}</p>
}
