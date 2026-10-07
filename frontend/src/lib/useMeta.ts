import { useQuery } from '@tanstack/react-query'
import { fetchMeta } from './api'

export function useMeta() {
  return useQuery({ queryKey: ['meta'], queryFn: fetchMeta, staleTime: Number.POSITIVE_INFINITY })
}
