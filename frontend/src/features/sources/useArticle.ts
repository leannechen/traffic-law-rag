import { useQuery } from '@tanstack/react-query'
import { fetchChunk } from '../../lib/api'

/** 條文全文：開啟面板或抽屜時才取，同一條只取一次（資料版本不變就不會變）。 */
export function useArticle(articleId: string) {
  return useQuery({
    queryKey: ['article', articleId],
    queryFn: () => fetchChunk(articleId),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  })
}
