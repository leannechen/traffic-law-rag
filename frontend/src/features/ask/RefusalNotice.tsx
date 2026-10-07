import { SearchOffIcon } from '../../components/icons'
import { EXAMPLE_QUESTIONS } from './examples'
import styles from './RefusalNotice.module.css'

type Props = {
  onAsk: (question: string) => void
  onNewQuestion: () => void
}

/** 拒答。「為什麼不回答」（步驟分支與相似度對照條）在 WhyRefused。 */
export function RefusalNotice({ onAsk, onNewQuestion }: Props) {
  return (
    <section aria-labelledby="refuse-title" className={styles.root}>
      <div className={styles.label}>
        <SearchOffIcon size={20} />
        查無依據，因此不作答
      </div>
      <h2 id="refuse-title" className={styles.title}>
        資料範圍內找不到相關規定
      </h2>
      <p className={styles.lede}>
        為了確保每句話都有條文依據，找不到足夠相關的條文時，系統會選擇不回答，而不是猜測。可能的原因：
      </p>
      <ul className={styles.reasons}>
        <li>問題涉及的法規不在收錄範圍內</li>
        <li>問法比較籠統，系統對應不到具體條文</li>
      </ul>
      <div className={styles.suggest}>
        <h3 className={styles.suggestTitle}>可以試著這樣問</h3>
        <div className={styles.chips}>
          {EXAMPLE_QUESTIONS.slice(0, 2).map((example) => (
            <button
              key={example.question}
              type="button"
              className={styles.chip}
              onClick={() => onAsk(example.question)}
            >
              {example.question}
            </button>
          ))}
          <button type="button" className={styles.chipNeutral} onClick={onNewQuestion}>
            換個問題
          </button>
        </div>
      </div>
    </section>
  )
}
