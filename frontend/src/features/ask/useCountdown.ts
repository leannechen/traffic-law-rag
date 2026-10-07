import { useEffect, useState } from 'react'

/** 秒數 → mm:ss */
export function formatCountdown(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

/** 從 seconds 倒數到 0，每秒更新。seconds 為 undefined 時固定回傳 0。 */
export function useCountdown(seconds: number | undefined): number {
  const [remaining, setRemaining] = useState(seconds ?? 0)

  useEffect(() => {
    setRemaining(seconds ?? 0)
    if (!seconds) return
    const endAt = Date.now() + seconds * 1000
    const timer = setInterval(() => {
      const left = Math.max(0, Math.ceil((endAt - Date.now()) / 1000))
      setRemaining(left)
      if (left === 0) clearInterval(timer)
    }, 250)
    return () => clearInterval(timer)
  }, [seconds])

  return remaining
}
