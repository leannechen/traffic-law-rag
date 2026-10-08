import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { Disclaimer } from '../components/Disclaimer'
import { PageShell } from '../components/PageShell'
import { ExampleQuestions } from '../features/ask/ExampleQuestions'
import { QuestionInput } from '../features/ask/QuestionInput'
import { ScopeSection } from '../features/ask/ScopeSection'
import styles from './HomeView.module.css'

export function HomeView({ onAsk }: { onAsk: (question: string) => void }) {
  const { hash } = useLocation()

  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView()
  }, [hash])

  return (
    <PageShell>
      <section className={styles.hero}>
        <p className={styles.kicker}>白話問答 · 條文為據</p>
        <h1 className={styles.title}>交通法規白話文搜尋</h1>
        <p className={styles.lede}>
          輸入你的問題，系統會找出相關條文，只根據條文回答，並標出每一句話的出處。
        </p>
        <QuestionInput onSubmit={onAsk} />
      </section>
      <ExampleQuestions onSelect={onAsk} />
      <ScopeSection />
      <Disclaimer />
    </PageShell>
  )
}
