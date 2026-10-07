import { type FormEvent, type KeyboardEvent, useId, useState } from 'react'
import { ArrowRightIcon } from '../../components/icons'
import styles from './QuestionInput.module.css'

export const MAX_QUESTION_LENGTH = 200

/** 與後端一致：以字元（code point）計，不含頭尾空白。 */
export function questionLength(value: string): number {
  return Array.from(value.trim()).length
}

type Props = { onSubmit: (question: string) => void }

export function QuestionInput({ onSubmit }: Props) {
  const id = useId()
  const [value, setValue] = useState('')
  const length = questionLength(value)
  const tooLong = length > MAX_QUESTION_LENGTH
  const canSubmit = length > 0 && !tooLong

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (canSubmit) onSubmit(value.trim())
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // 輸入法選字中的 Enter 不送出
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form className={styles.root} onSubmit={submit}>
      <label htmlFor={id} className={styles.label}>
        你的問題
      </label>
      <div className={`${styles.field} ${tooLong ? styles.invalid : ''}`}>
        <textarea
          id={id}
          className={styles.input}
          rows={2}
          value={value}
          placeholder="例如：騎機車沒戴安全帽會被罰多少？"
          aria-invalid={tooLong}
          aria-describedby={`${id}-help`}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" className={styles.submit} disabled={!canSubmit}>
          提問
          <ArrowRightIcon size={18} />
        </button>
      </div>
      <div id={`${id}-help`} className={`${styles.help} ${tooLong ? styles.helpInvalid : ''}`}>
        <span>
          {tooLong
            ? `⨯ 問題超過 ${MAX_QUESTION_LENGTH} 字，請精簡成一個重點。`
            : '一次問一題，可以用口語描述情境。'}
        </span>
        <span>
          {length} / {MAX_QUESTION_LENGTH}
        </span>
      </div>
    </form>
  )
}
