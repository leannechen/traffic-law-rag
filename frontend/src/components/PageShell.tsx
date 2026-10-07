import type { ReactNode } from 'react'
import styles from './PageShell.module.css'

export function PageShell({ children }: { children: ReactNode }) {
  return <main className={styles.root}>{children}</main>
}
