import { useState } from 'react'
import { applyMode, nextMode, readMode, saveMode, THEME_LABEL, type ThemeMode } from '../lib/theme'
import { MonitorIcon, MoonIcon, SunIcon } from './icons'
import styles from './ThemeToggle.module.css'

const ICONS = { system: MonitorIcon, light: SunIcon, dark: MoonIcon }

/**
 * 外觀切換：跟隨系統 → 亮色 → 暗色。一個按鈕輪流切換，選擇記在瀏覽器。
 * 按鈕文字是「目前」的外觀；螢幕閱讀器另外聽到「點一下會切換成什麼」。
 */
export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(readMode)
  const Icon = ICONS[mode]

  function cycle() {
    const next = nextMode(mode)
    setMode(next)
    applyMode(next)
    saveMode(next)
  }

  return (
    <button
      type="button"
      className={styles.root}
      onClick={cycle}
      aria-label={`外觀：${THEME_LABEL[mode]}，點一下切換為${THEME_LABEL[nextMode(mode)]}`}
    >
      <Icon size={18} />
      <span aria-hidden="true">{THEME_LABEL[mode]}</span>
    </button>
  )
}
