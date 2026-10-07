import type { IndexMeta } from '../types/meta'

export async function fetchMeta(): Promise<IndexMeta> {
  const res = await fetch('/api/meta')
  if (!res.ok) throw new Error(`meta request failed: ${res.status}`)
  return res.json()
}
