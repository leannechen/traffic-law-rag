import styles from './MetricCard.module.css'

type Props = {
  name: string
  code: string
  value: string
  description: string
}

/** 單一指標：中文名稱、英文代號、數值、一句白話說明。 */
export function MetricCard({ name, code, value, description }: Props) {
  return (
    <div className={styles.root}>
      <span className={styles.name}>{name}</span>
      <span className={styles.code}>{code}</span>
      <span className={styles.value}>{value}</span>
      <span className={styles.description}>{description}</span>
    </div>
  )
}
