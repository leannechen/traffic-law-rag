import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { GITHUB_URL } from '../lib/config'
import { useMeta } from '../lib/useMeta'
import styles from './Header.module.css'
import { CloseIcon, GitHubIcon, MenuIcon } from './icons'
import { ThemeToggle } from './ThemeToggle'

// repo 公開之前先不在畫面上顯示 GitHub 連結；公開後改成 true
const SHOW_GITHUB_LINK = true

type Props = {
  /** 首頁（尚未提問）用置中的大刊頭；其他頁面與狀態用精簡頁首 */
  masthead: boolean
}

export function Header({ masthead }: Props) {
  const { data: meta } = useMeta()
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname, hash } = useLocation()

  // 換頁後收起手機選單；pathname、hash 變動就是要重跑
  // biome-ignore lint/correctness/useExhaustiveDependencies: 以路由變動作為觸發條件
  useEffect(() => setMenuOpen(false), [pathname, hash])

  const updated = meta ? meta.data_version : '—'

  return (
    <header className={`${styles.root} ${masthead ? styles.masthead : ''}`}>
      <div className={styles.band}>
        <div className={styles.bandInner}>
          <span className={styles.bandMobile}>
            {meta ? `收錄 ${meta.laws.length} 部法規 · 資料更新 ${updated}` : '資料載入中…'}
          </span>
          <span className={styles.bandDesktop}>
            <strong>{masthead ? '收錄法規' : '收錄：'}</strong>
            {meta?.laws.map((law, i) => (
              <span key={law.pcode} className={styles.law}>
                {!masthead && i > 0 && ' · '}
                {law.law_short_name}
                {masthead && <span className={styles.level}> {law.law_level}</span>}
              </span>
            ))}
          </span>
          <span className={styles.updated}>資料更新：{updated}</span>
        </div>
      </div>

      <div className={styles.bar}>
        <div className={styles.barInner}>
          <Link to="/" className={styles.title}>
            交通法規資料庫
          </Link>
          <button
            type="button"
            className={styles.menuButton}
            aria-label={menuOpen ? '關閉選單' : '開啟選單'}
            aria-expanded={menuOpen}
            aria-controls="main-nav"
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <CloseIcon size={22} /> : <MenuIcon size={22} />}
          </button>
        </div>
        <nav
          id="main-nav"
          aria-label="主選單"
          className={`${styles.nav} ${menuOpen ? styles.navOpen : ''}`}
        >
          <NavLink to="/" end className={navClass}>
            問答
          </NavLink>
          <Link to={{ pathname: '/', hash: '#scope' }} className={styles.link}>
            收錄範圍
          </Link>
          <NavLink to="/eval" className={navClass}>
            評估結果
          </NavLink>
          <NavLink to="/about" className={navClass}>
            關於
          </NavLink>
          <ThemeToggle />
          {masthead && SHOW_GITHUB_LINK && (
            <a
              className={styles.github}
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              aria-label="GitHub 原始碼（另開新視窗）"
              title="GitHub 原始碼"
            >
              <GitHubIcon size={18} />
            </a>
          )}
        </nav>
      </div>
    </header>
  )
}

function navClass({ isActive }: { isActive: boolean }): string {
  return `${styles.link} ${isActive ? styles.active : ''}`
}
