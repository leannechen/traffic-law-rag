export type ThemeMode = 'system' | 'light' | 'dark'

const KEY = 'theme'

/** 切換順序：跟隨系統 → 亮色 → 暗色 → 跟隨系統 */
export const THEME_ORDER: readonly ThemeMode[] = ['system', 'light', 'dark']

export const THEME_LABEL: Record<ThemeMode, string> = {
  system: '跟隨系統',
  light: '亮色',
  dark: '暗色',
}

export function nextMode(mode: ThemeMode): ThemeMode {
  return THEME_ORDER[(THEME_ORDER.indexOf(mode) + 1) % THEME_ORDER.length]
}

/** 讀使用者上次選的外觀；讀不到（無痕視窗、禁用儲存）就跟隨系統。 */
export function readMode(): ThemeMode {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

export function saveMode(mode: ThemeMode): void {
  try {
    if (mode === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, mode)
  } catch {
    // 無法儲存也沒關係：這次瀏覽仍然有效，只是下次不會記得
  }
}

/** 套到 <html data-theme>；跟隨系統就移除屬性，交給 prefers-color-scheme。 */
export function applyMode(mode: ThemeMode): void {
  const root = document.documentElement
  if (mode === 'system') delete root.dataset.theme
  else root.dataset.theme = mode
}
