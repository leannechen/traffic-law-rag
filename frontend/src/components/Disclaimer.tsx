import styles from './Disclaimer.module.css'
import { InfoIcon } from './icons'

/** 完整版免責聲明（首頁、關於頁）。每頁頁尾另有精簡版。 */
export function Disclaimer({ variant = 'aside' }: { variant?: 'aside' | 'box' }) {
  return (
    <aside className={`${styles.root} ${variant === 'box' ? styles.box : ''}`}>
      {variant === 'aside' && <InfoIcon size={18} className={styles.icon} />}
      <p>
        <strong>免責聲明</strong>
        <span className={styles.gap} />
        本工具僅整理並引用公開法規條文，不構成法律意見。法規可能修正，實際適用以主管機關公告及全國法規資料庫最新內容為準。
      </p>
    </aside>
  )
}
