import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useAskContext } from '../features/ask/AskContext'
import { Footer } from './Footer'
import { Header } from './Header'

export function Layout() {
  const { question } = useAskContext()
  const { pathname, hash } = useLocation()
  const masthead = pathname === '/' && !question

  // 換頁時回到頁面頂端；有 hash（#scope）的由該頁自己捲動
  // biome-ignore lint/correctness/useExhaustiveDependencies: 以路由變動作為觸發條件
  useEffect(() => {
    if (!hash) window.scrollTo(0, 0)
  }, [pathname])

  return (
    <>
      <Header masthead={masthead} />
      <Outlet />
      <Footer />
    </>
  )
}
