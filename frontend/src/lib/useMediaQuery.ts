import { useSyncExternalStore } from 'react'

/** 桌面／手機版面的切換：全文面板與條文抽屜是兩套不同的元件，同一時間只放一套進 DOM。 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      const list = window.matchMedia(query)
      list.addEventListener('change', notify)
      return () => list.removeEventListener('change', notify)
    },
    () => window.matchMedia(query).matches,
    () => false,
  )
}

export const MOBILE_QUERY = '(max-width: 767px)'
