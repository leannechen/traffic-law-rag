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
      {laws.length > 0 && (
        <table className={styles.table}>
          <caption className={styles.caption}>收錄法規</caption>
          <thead>
            <tr>
              <th scope="col">類別</th>
              <th scope="col">法規名稱</th>
              <th scope="col">簡稱</th>
              <th scope="col" className={styles.num}>
                條文數
              </th>
              <th scope="col">最新異動</th>
            </tr>
          </thead>
          <tbody>
            {laws.map((law) => (
              <tr key={law.pcode}>
                <td className={styles.levelCell}>
                  <span className={styles.level}>{law.law_level}</span>
                </td>
                <th scope="row" className={styles.name}>
                  {law.law_name}
                </th>
                <td className={styles.short}>{law.law_short_name}</td>
                <td className={`${styles.num} ${styles.meta}`}>{law.article_count} 條</td>
                <td className={styles.meta}>{formatDate(law.amended_date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
