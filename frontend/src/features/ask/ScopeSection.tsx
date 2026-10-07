import { formatDate } from '../../lib/format'
import { useMeta } from '../../lib/useMeta'
import styles from './ScopeSection.module.css'

export function ScopeSection() {
  const { data: meta, isError } = useMeta()
  const laws = meta?.laws ?? []
  return (
    <section id="scope" aria-labelledby="scope-title" className={styles.root}>
      <div className={styles.head}>
        <h2 id="scope-title" className={styles.title}>
          收錄範圍
        </h2>
        {meta && <span className={styles.updated}>資料更新：{meta.data_version}</span>}
      </div>
      <p className={styles.lede}>
        {laws.length > 0
          ? `只根據以下${laws.length}部法規回答；範圍外的問題，系統會明確告知找不到相關規定。`
          : '範圍外的問題，系統會明確告知找不到相關規定。'}
      </p>
      {isError && <p className={styles.error}>暫時無法取得收錄法規清單。</p>}
      <ul className={styles.grid}>
        {laws.map((law) => (
          <li key={law.pcode} className={styles.law}>
            <span className={styles.level}>{law.law_level}</span>
            <h3 className={styles.name}>{law.law_name}</h3>
            <span className={styles.short}>簡稱：{law.law_short_name}</span>
            <span className={styles.stats}>
              {law.article_count} 條 · 最新異動 {formatDate(law.amended_date)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
