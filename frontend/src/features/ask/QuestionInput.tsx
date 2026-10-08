import { type FormEvent, type KeyboardEvent, useId, useLayoutEffect, useRef, useState } from 'react'
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
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [value, setValue] = useState('')
  const length = questionLength(value)
  const tooLong = length > MAX_QUESTION_LENGTH
  const canSubmit = !tooLong

  // 高度跟著內容長：固定高度加上換行（Shift+Enter 或超過一行）會出現多餘的捲軸。
  // 超過最大高度才捲動。value 變動就是要重算。
  // biome-ignore lint/correctness/useExhaustiveDependencies: 以輸入內容作為觸發條件
  useLayoutEffect(() => {
    const el = inputRef.current
    if (!el || el.scrollHeight === 0) return // jsdom 沒有排版，量不到
    // 先縮到 0 再量：height:auto 會以 rows 屬性的行數為底，桌面就會多出一行。
    // 最小高度（桌面 1 行、手機 2 行）由 CSS 的 min-height 保證。
    el.style.height = '0px'
    const max = Number.parseFloat(getComputedStyle(el).maxHeight)
    const next = Number.isFinite(max) ? Math.min(el.scrollHeight, max) : el.scrollHeight
    el.style.height = `${next}px`
    el.style.overflowY = el.scrollHeight > next ? 'auto' : 'hidden'
  }, [value])

  function submit(event?: FormEvent) {
    event?.preventDefault()
    // 空白時按鈕看起來和平常一樣（畫板如此），按下去只是把游標帶回輸入框
    if (length === 0) inputRef.current?.focus()
    else if (canSubmit) onSubmit(value.trim())
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // 輸入法選字中的 Enter 不送出
    // Safari 在選字完成的那次 Enter 會回報 isComposing=false、keyCode=229，兩個都要擋
    const composing = event.nativeEvent.isComposing || event.keyCode === 229
    if (event.key === 'Enter' && !event.shiftKey && !composing) {
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
          ref={inputRef}
          className={styles.input}
          rows={2}
          value={value}
          placeholder="例如：騎機車沒戴安全帽會被罰多少？"
          aria-invalid={tooLong}
          aria-describedby={`${id}-help`}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" className={styles.submit} disabled={tooLong}>
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
