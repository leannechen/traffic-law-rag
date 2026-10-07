import { ArrowRightIcon } from '../../components/icons'
import styles from './ExampleQuestions.module.css'
import { EXAMPLE_QUESTIONS } from './examples'

export function ExampleQuestions({ onSelect }: { onSelect: (question: string) => void }) {
  return (
    <section aria-labelledby="examples" className={styles.root}>
      <h2 id="examples" className={styles.title}>
        試試這些問題
      </h2>
      <ul className={styles.list}>
        {EXAMPLE_QUESTIONS.map((example) => (
          <li key={example.question} className={styles.item}>
            <button
              type="button"
              className={styles.button}
              onClick={() => onSelect(example.question)}
            >
              <span className={styles.category}>{example.category}</span>
              <span className={styles.question}>
                {example.question}
                <ArrowRightIcon size={16} className={styles.arrow} />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
