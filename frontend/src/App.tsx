import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from './lib/api'

export function healthLabel(status: 'pending' | 'error' | 'success'): string {
  if (status === 'success') return '後端連線正常'
  if (status === 'error') return '後端無法連線'
  return '檢查中…'
}

export default function App() {
  const { status } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, retry: false })
  return (
    <main>
      <h1>交通法規資料庫</h1>
      <p role="status">{healthLabel(status)}</p>
    </main>
  )
}
