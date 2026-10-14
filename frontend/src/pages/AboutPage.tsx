import type { ReactNode } from 'react'
import { Disclaimer } from '../components/Disclaimer'
import { Icon } from '../components/icons'
import { PageShell } from '../components/PageShell'
import { GITHUB_URL } from '../lib/config'
import { useMeta } from '../lib/useMeta'
import styles from './AboutPage.module.css'

const DOES = [
  '找出和問題相關的條文，並列出相似度',
  '用白話整理條文內容，每個論點附出處',
  '答案中的金額、點數直接取自條文原文',
  '找不到依據時明確告知，不勉強作答',
]

const DOES_NOT = [
  '提供法律意見或判斷個案',
  '引用法院判決、行政函釋',
  '回答收錄範圍以外的法規',
  '記錄你的問題或個人資料',
]

type HowStep = { title: string; text: string; icon: ReactNode }

const HOW: HowStep[] = [
  {
    title: '改寫問題',
    text: '把口語轉成法律用語查詢（目前預設關閉）',
    icon: (
      <Icon size={26} strokeWidth={1.6}>
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
      </Icon>
    ),
  },
  {
    title: '檢索條文',
    text: '用語意向量找出最相近的前幾名',
    icon: (
      <Icon size={26} strokeWidth={1.6}>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
      </Icon>
    ),
  },
  {
    title: '相關度檢查',
    text: '不夠相關就拒答',
    icon: (
      <Icon size={26} strokeWidth={1.6}>
        <path d="M3 5h18l-7 8v6l-4-2v-4Z" />
      </Icon>
    ),
  },
  {
    title: '產生答案',
    text: '只根據條文，附上出處',
    icon: (
      <Icon size={26} strokeWidth={1.6}>
        <path d="M4 5h16v11H9l-5 4Z" />
        <path d="M8 9h8" />
        <path d="M8 12h5" />
      </Icon>
    ),
  },
  {
    title: '驗證引用',
    text: '確認出處真的在檢索結果中',
    icon: (
      <Icon size={26} strokeWidth={1.6}>
        <path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6Z" />
        <path d="m9 12 2 2 4-4" />
      </Icon>
    ),
  },
]

export function AboutPage() {
  const { data: meta } = useMeta()
  return (
    <PageShell>
      <div className={styles.root}>
        <section className={styles.intro}>
          <p className={styles.kicker}>關於本工具</p>
          <h1 className={styles.title}>
            只根據條文回答，
            <br />
            附上參考依據。
          </h1>
          <p className={styles.lede}>
            交通法規用語艱澀，關鍵字搜尋常常對不上白話問題。這個工具把你的問題對應到相關條文，只根據條文回答，並附上每一句話的出處。
          </p>
        </section>

        <section className={styles.does}>
          <div className={styles.doesCol}>
            <h2 className={styles.h2}>它會做的事</h2>
            <ul>
              {DOES.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div className={`${styles.doesCol} ${styles.doesNot}`}>
            <h2 className={styles.h2}>它不會做的事</h2>
            <ul>
              {DOES_NOT.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </section>

        <section aria-labelledby="how" className={styles.how}>
          <h2 id="how" className={styles.h2Big}>
            運作方式
          </h2>
          <ol className={styles.steps}>
            {HOW.map((step, i) => (
              <li key={step.title} className={styles.step}>
                <span className={styles.stepHead}>
                  <span className={styles.stepIcon}>{step.icon}</span>
                  <span className={styles.stepNo}>{String(i + 1).padStart(2, '0')}</span>
                </span>
                <strong>{step.title}</strong>
                <span className={styles.stepText}>{step.text}</span>
              </li>
            ))}
          </ol>
        </section>

        <section className={styles.source}>
          <div className={styles.sourceMain}>
            <h2 className={styles.h2}>資料來源與授權</h2>
            <p>
              法規資料來源：全國法規資料庫（
              <a href="https://law.moj.gov.tw/" target="_blank" rel="noreferrer">
                https://law.moj.gov.tw/
              </a>
              ），由法務部依政府資料開放授權條款授權使用。
              {meta && `目前版本為 ${meta.data_version}。`}
            </p>
            <Disclaimer variant="box" />
          </div>
          <div className={styles.sourceCode}>
            <h2 className={styles.h2}>原始碼</h2>
            <p>架構、技術取捨與評估方法都寫在 README。</p>
            <a className={styles.github} href={GITHUB_URL} target="_blank" rel="noreferrer">
              前往 GitHub
            </a>
          </div>
        </section>
      </div>
    </PageShell>
  )
}
