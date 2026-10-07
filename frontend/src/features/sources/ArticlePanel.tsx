import { useEffect, useRef } from 'react'
import { CloseIcon } from '../../components/icons'
import { formatDate } from '../../lib/format'
import type { ArticleEvidence } from '../ask/articles'
import { ArticleBody } from './ArticleBody'
import styles from './ArticlePanel.module.css'

type Props = {
  article: ArticleEvidence
  cited: boolean
  onClose: () => void
}

/** 桌面的下方全文面板：不是 modal，沒有遮罩、不鎖住頁面（頁面底部會留出面板高度的空白）。 */
export function ArticlePanel({ article, cited, onClose }: Props) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const title = `${article.lawShortName} 第 ${article.articleNo} 條`

  // 開啟時把焦點帶進面板（關閉後由呼叫端還給原本的元素）
  useEffect(() => headingRef.current?.focus(), [])

  // 切換條文時，內文捲回頂端
  // biome-ignore lint/correctness/useExhaustiveDependencies: 以條文變動作為觸發條件
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = 0
  }, [article.articleId])

  return (
    <section aria-label="條文全文" className={styles.root}>
      <div className={styles.bar}>
        <div className={styles.barInner}>
          <span className={styles.label}>條文全文</span>
          <span aria-hidden="true" className={styles.divider} />
          <span className={styles.barTitle}>{title}</span>
          <a
            className={styles.external}
            href={article.sourceUrl}
            target="_blank"
            rel="noreferrer"
            aria-label={`在全國法規資料庫查看${title}（另開新視窗）`}
          >
            在全國法規資料庫查看 ↗
          </a>
          <button
            type="button"
            className={styles.close}
            aria-label="關閉條文全文"
            onClick={onClose}
          >
            <CloseIcon size={22} />
          </button>
        </div>
      </div>
      <div className={styles.content}>
        <div className={styles.side}>
          <span className={cited ? styles.tagCited : styles.tagPlain}>
            {cited ? '已引用' : '檢索到'}
          </span>
          <p className={styles.law}>{article.lawName}</p>
          <h2 ref={headingRef} tabIndex={-1} className={styles.heading}>
            第 {article.articleNo} 條
          </h2>
          <p className={styles.amended}>最新異動 {formatDate(article.amendedDate)}</p>
        </div>
        <section
          ref={bodyRef}
          className={styles.body}
          aria-label="條文全文，可捲動"
          // biome-ignore lint/a11y/noNoninteractiveTabindex: 可捲動區域要能用鍵盤捲動
          tabIndex={0}
        >
          <ArticleBody articleId={article.articleId} sourceUrl={article.sourceUrl} />
        </section>
      </div>
    </section>
  )
}
