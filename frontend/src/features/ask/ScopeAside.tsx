import { useMeta } from '../../lib/useMeta'
import styles from './ScopeAside.module.css'

/** 拒答頁右欄「目前收錄的法規」 */
export function ScopeAside() {
  const { data: meta } = useMeta()
  const laws = meta?.laws ?? []
  return (
    <aside aria-label="收錄範圍" className={styles.root}>
      <div className={styles.head}>
        <h2 className={styles.title}>目前收錄的法規</h2>
      </div>
      <p className={styles.lede}>
        {laws.length > 0 ? `系統只根據這${laws.length}部法規回答。` : '系統只根據收錄的法規回答。'}
      </p>
      <ul className={styles.list}>
        {laws.map((law) => (
          <li key={law.pcode} className={styles.item}>
            <span className={styles.name}>{law.law_name}</span>
            <span className={styles.level}>{law.law_level}</span>
          </li>
        ))}
      </ul>
      <p className={styles.lede}>
        需要其他法規？可直接到{' '}
        <a href="https://law.moj.gov.tw/" target="_blank" rel="noreferrer">
          全國法規資料庫
        </a>{' '}
        查詢。
      </p>
    </aside>
  )
}
