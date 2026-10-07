import type { RetrievalItem } from '../../types/events'

/** chunk_id 去掉 `-p{n}`（依項切分的後綴）就是條的 id；answer.citation 的 chunk_id 本來就是條。 */
export function articleIdOf(chunkId: string): string {
  return chunkId.replace(/-p\d+$/, '')
}

export type ArticleEvidence = {
  articleId: string
  lawShortName: string
  lawName: string
  articleNo: string
  score: number
  snippet: string
  sourceUrl: string
  amendedDate: string
}

/** 依據以「條」為單位：同一條被切成多個 chunk 時只留一張（取最高分）。順序為檢索名次。 */
export function groupArticles(items: RetrievalItem[]): ArticleEvidence[] {
  const byArticle = new Map<string, ArticleEvidence>()
  for (const item of [...items].sort((a, b) => a.rank - b.rank)) {
    const articleId = articleIdOf(item.chunk_id)
    const existing = byArticle.get(articleId)
    if (existing && existing.score >= item.score) continue
    byArticle.set(articleId, {
      articleId,
      lawShortName: item.law_short_name,
      lawName: item.law_name,
      articleNo: item.article_no,
      score: item.score,
      snippet: item.snippet,
      sourceUrl: item.source_url,
      amendedDate: item.amended_date,
    })
  }
  return [...byArticle.values()]
}

/** 完成時：已引用的在上、未引用的在下，組內維持檢索順序（即依分數）。 */
export function sortForDone(evidence: ArticleEvidence[], cited: string[]): ArticleEvidence[] {
  const isCited = (e: ArticleEvidence) => cited.includes(e.articleId)
  return [...evidence.filter(isCited), ...evidence.filter((e) => !isCited(e))]
}
