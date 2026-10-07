import { Link } from 'react-router-dom'
import { AlertIcon, ClockIcon } from '../../components/icons'
import type { AskError } from './askReducer'
import styles from './ErrorNotice.module.css'
import { formatCountdown, useCountdown } from './useCountdown'

type Props = {
  error: AskError
  runId: string | null
  onRetry: () => void
  onHome: () => void
}

const COPY: Record<string, { label: string; title: string; body: string }> = {
  stream_interrupted: {
    label: '連線中斷',
    title: '答案沒有完整送達',
    body: '和伺服器的連線在產生答案時中斷了。已顯示的內容可能不完整，請重新送出問題。',
  },
  network_error: {
    label: '無法連線',
    title: '連不上伺服器',
    body: '請確認網路連線後再試一次。',
  },
  llm_error: {
    label: '服務暫時無法使用',
    title: '回答服務暫時無法使用',
    body: '產生答案的服務暫時沒有回應，請稍後重試。已顯示的內容可能不完整。',
  },
  embedding_error: {
    label: '服務暫時無法使用',
    title: '檢索服務暫時無法使用',
    body: '找不到相關條文的服務暫時沒有回應，請稍後重試。',
  },
  truncated: {
    label: '答案不完整',
    title: '答案太長，被截斷了',
    body: '請把問題問得更具體一點再問一次。已顯示的內容不完整。',
  },
  internal_error: {
    label: '發生錯誤',
    title: '發生未預期的錯誤',
    body: '伺服器處理這個問題時出了問題，請稍後重試。',
  },
  invalid_question: {
    label: '問題無法送出',
    title: '問題格式不符',
    body: '請確認問題不是空白，且不超過 200 字。',
  },
  http_error: {
    label: '發生錯誤',
    title: '伺服器回應異常',
    body: '請稍後重試。',
  },
}

export function ErrorNotice({ error, runId, onRetry, onHome }: Props) {
  const remaining = useCountdown(error.code === 'rate_limited' ? error.retryAfter : undefined)

  if (error.code === 'rate_limited') {
    return (
      <div role="status" className={`${styles.root} ${styles.warn}`}>
        <div className={styles.label}>
          <ClockIcon size={18} />
          請稍候
        </div>
        <h2 className={styles.title}>提問太頻繁，請稍後再試</h2>
        <p className={styles.body}>為了讓每個人都能使用，每分鐘的提問次數有上限。</p>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.primary}
            disabled={remaining > 0}
            onClick={onRetry}
          >
            重試
          </button>
          {remaining > 0 && (
            <span className={styles.countdown} aria-hidden="true">
              {formatCountdown(remaining)} 後可再提問
            </span>
          )}
        </div>
      </div>
    )
  }

  const copy = COPY[error.code] ?? COPY.http_error
  return (
    <div role="alert" className={`${styles.root} ${styles.err}`}>
      <div className={styles.label}>
        <AlertIcon size={18} />
        {copy.label}
      </div>
      <h2 className={styles.title}>{copy.title}</h2>
      <p className={styles.body}>
        {error.code === 'invalid_question' && error.message ? error.message : copy.body}
      </p>
      <div className={styles.actions}>
        {error.code !== 'invalid_question' && (
          <button type="button" className={styles.primary} onClick={onRetry}>
            重試
          </button>
        )}
        <Link to="/" className={styles.secondary} onClick={onHome}>
          回首頁
        </Link>
      </div>
      <p className={styles.code}>
        錯誤代碼 {error.code}
        {runId ? ` · run ${runId.slice(0, 4)}` : ''}
      </p>
    </div>
  )
}
