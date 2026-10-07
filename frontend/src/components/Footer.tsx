import styles from './Footer.module.css'

export function Footer() {
  return (
    <footer className={styles.root}>
      <div className={styles.inner}>
        <p className={styles.source}>
          法規資料來源：全國法規資料庫（
          <a href="https://law.moj.gov.tw/" target="_blank" rel="noreferrer">
            https://law.moj.gov.tw/
          </a>
          ），由法務部依政府資料開放授權條款授權使用。
        </p>
        <p className={styles.note}>僅供參考，非法律意見。</p>
      </div>
    </footer>
  )
}
