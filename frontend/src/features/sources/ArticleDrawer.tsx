import { type KeyboardEvent, useEffect, useRef } from 'react'
import { CloseIcon } from '../../components/icons'
import { formatDate } from '../../lib/format'
import type { ArticleEvidence } from '../ask/articles'
import { ArticleBody } from './ArticleBody'
import styles from './ArticleDrawer.module.css'

type Props = {
  articles: ArticleEvidence[]
  index: number
  cited: boolean
  onClose: () => void
  onNavigate: (articleId: string) => void
}

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** 手機的底部抽屜（dialog，有遮罩）。「上一則／下一則」在本次檢索到的條文間切換。 */
export function ArticleDrawer({ articles, index, cited, onClose, onNavigate }: Props) {
  const article = articles[index]
  const rootRef = useRef<HTMLDivElement>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  // 開啟時焦點進入抽屜、背景頁面不捲動
  useEffect(() => {
    titleRef.current?.focus()
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [])

  // biome-ignore lint/correctness/useExhaustiveDependencies: 以條文變動作為觸發條件
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = 0
  }, [article?.articleId])

  if (!article) return null
  const title = `${article.lawShortName} 第 ${article.articleNo} 條`

  // 焦點只在抽屜內循環（aria-modal 不會自動幫我們做）
  function trapFocus(event: KeyboardEvent) {
    if (event.key !== 'Tab' || !rootRef.current) return
    const items = [...rootRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)]
    const first = items[0]
    const last = items[items.length - 1]
    if (!first || !last) return
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <>
      <div className={styles.scrim} aria-hidden="true" onClick={onClose} />
      <div
        ref={rootRef}
        className={styles.root}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        onKeyDown={trapFocus}
      >
        <div className={styles.handle} aria-hidden="true" />
        <div className={styles.head}>
          <span className={cited ? styles.tagCited : styles.tagPlain}>
            {cited ? '已引用' : '檢索到'}
          </span>
          <h2 id="drawer-title" ref={titleRef} tabIndex={-1} className={styles.title}>
            {title}
          </h2>
          <button
            type="button"
            className={styles.close}
            aria-label="關閉條文全文"
            onClick={onClose}
          >
            <CloseIcon size={22} />
          </button>
        </div>
        <div ref={bodyRef} className={styles.body}>
          <ArticleBody articleId={article.articleId} sourceUrl={article.sourceUrl} />
          <p className={styles.amended}>最新異動 {formatDate(article.amendedDate)}</p>
          <a
            className={styles.external}
            href={article.sourceUrl}
            target="_blank"
            rel="noreferrer"
            aria-label={`在全國法規資料庫查看${title}（另開新視窗）`}
          >
            在全國法規資料庫查看 ↗
          </a>
        </div>
        <div className={styles.nav}>
          <button
            type="button"
            className={styles.navButton}
            disabled={index === 0}
            onClick={() => onNavigate(articles[index - 1].articleId)}
          >
            ← 上一則
          </button>
          <button
            type="button"
            className={styles.navButton}
            disabled={index === articles.length - 1}
            onClick={() => onNavigate(articles[index + 1].articleId)}
          >
            下一則 →
          </button>
        </div>
      </div>
    </>
  )
}
