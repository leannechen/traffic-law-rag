import type { ChunkDetail } from '../types/chunk'
import type { IndexMeta } from '../types/meta'

export async function fetchMeta(): Promise<IndexMeta> {
  const res = await fetch('/api/meta')
  if (!res.ok) throw new Error(`meta request failed: ${res.status}`)
  return res.json()
}

export async function fetchChunk(id: string): Promise<ChunkDetail> {
  const res = await fetch(`/api/chunks/${encodeURIComponent(id)}`)
  if (!res.ok) throw new Error(`chunk request failed: ${res.status}`)
  return res.json()
}
