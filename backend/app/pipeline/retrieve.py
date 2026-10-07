"""向量檢索：問題 → query embedding → Chroma → 以「條」去重的 top-k。

uv run python -m app.pipeline.retrieve "紅燈右轉罰多少"
"""

import argparse
from typing import Any

import chromadb

from app.core.config import get_settings
from app.core.embedder import CachedEmbedder, Embedder, VoyageEmbedder
from app.ingestion.build_index import COLLECTION
from app.pipeline.bm25 import BM25Index, Tokenizer
from app.schemas.retrieval import RetrievedChunk

# 同一條可能被切成多塊、同時占住前幾名，所以先多取再去重。
OVERFETCH = 3
RRF_K = 60  # RRF 常數：越大，名次差異的影響越小
FUSION_DEPTH = 20  # 各自取前 20 條再合併


def _to_hit(
    rank: int,
    score: float,
    chunk_id: str,
    text: str,
    meta: Any,
    vector_score: float | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        rank=rank,
        score=score,
        vector_score=vector_score,
        chunk_id=chunk_id,
        article_id=f"{meta['pcode']}:{meta['article_no']}",
        pcode=str(meta["pcode"]),
        law_name=str(meta.get("law_name", "")),
        law_short_name=str(meta["law_short_name"]),
        article_no=str(meta["article_no"]),
        source_url=str(meta.get("source_url", "")),
        amended_date=str(meta.get("amended_date", "")),
        text=text,
    )


class Retriever:
    def __init__(self, collection: Any, embedder: Embedder) -> None:
        self._collection = collection
        self._embedder = embedder

    @classmethod
    def from_settings(cls, *, disk_cache: bool = True) -> "Retriever":
        """disk_cache=True 時把問題的 embedding 存在本機檔案（評估與 CLI 用）。
        線上服務必須用 False：多個請求同時寫同一個檔案會互相覆蓋，也不該把使用者的問題落地。"""
        settings = get_settings()
        collection = chromadb.PersistentClient(path=str(settings.index_dir)).get_collection(
            COLLECTION
        )
        embedder: Embedder = VoyageEmbedder(settings.voyage_api_key, settings.embedding_model)
        if disk_cache:
            embedder = CachedEmbedder(embedder, settings.cache_dir / "query_embeddings.json")
        return cls(collection, embedder)

    def search(self, question: str, k: int = 5) -> list[RetrievedChunk]:
        """回傳最多 k 條（同一條只留最高分的那一塊），依分數由高到低。"""
        (vector,) = self._embedder.embed([question], "query")
        total = self._collection.count()
        n = min(k * OVERFETCH, total)
        while True:
            hits = self._query(vector, n, k)
            # 長條文被切成多塊時，前 n 塊可能集中在少數幾條；去重後不足 k 條就擴大取回量
            if len(hits) >= k or n >= total:
                return hits
            n = min(n * 2, total)

    def _query(self, vector: list[float], n: int, k: int) -> list[RetrievedChunk]:
        result = self._collection.query(
            query_embeddings=[vector],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        seen: set[str] = set()
        hits: list[RetrievedChunk] = []
        for chunk_id, doc, meta, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
            strict=True,
        ):
            article_id = f"{meta['pcode']}:{meta['article_no']}"
            if article_id in seen:
                continue
            seen.add(article_id)
            cosine = round(1 - distance, 4)
            hits.append(_to_hit(len(hits) + 1, cosine, chunk_id, doc, meta, vector_score=cosine))
            if len(hits) == k:
                break
        return hits


def rrf(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion：只看名次不看分數。每份榜單給 1/(k+名次)，加總後排序。"""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


class HybridRetriever:
    """向量檢索 + BM25，各取前 FUSION_DEPTH 條，以 RRF 合併。"""

    def __init__(self, vector: Retriever, collection: Any, tokenizer: Tokenizer = "jieba") -> None:
        self._vector = vector
        got = collection.get(include=["documents", "metadatas"])
        order = sorted(range(len(got["ids"])), key=lambda i: got["ids"][i])
        self._ids = [got["ids"][i] for i in order]
        self._docs = [got["documents"][i] for i in order]
        self._metas = [got["metadatas"][i] for i in order]
        self._bm25 = BM25Index(self._docs, tokenizer)

    @classmethod
    def from_settings(cls, tokenizer: Tokenizer = "jieba") -> "HybridRetriever":
        vector = Retriever.from_settings()
        return cls(vector, vector._collection, tokenizer)

    def _bm25_articles(self, question: str) -> list[RetrievedChunk]:
        seen: set[str] = set()
        hits: list[RetrievedChunk] = []
        for i, score in self._bm25.search(question, len(self._ids)):
            meta = self._metas[i]
            article_id = f"{meta['pcode']}:{meta['article_no']}"
            if article_id in seen:
                continue
            seen.add(article_id)
            hits.append(_to_hit(len(hits) + 1, round(score, 4), self._ids[i], self._docs[i], meta))
            if len(hits) == FUSION_DEPTH:
                break
        return hits

    def search(self, question: str, k: int = 5) -> list[RetrievedChunk]:
        by_vector = self._vector.search(question, FUSION_DEPTH)
        by_bm25 = self._bm25_articles(question)
        fused = rrf([[h.article_id for h in by_vector], [h.article_id for h in by_bm25]])
        vec = {h.article_id: h for h in by_vector}
        kw = {h.article_id: h for h in by_bm25}
        hits: list[RetrievedChunk] = []
        for article_id, score in fused[:k]:
            base = vec.get(article_id) or kw[article_id]
            hits.append(
                base.model_copy(
                    update={
                        "rank": len(hits) + 1,
                        "score": round(score, 5),
                        "vector_score": vec[article_id].score if article_id in vec else None,
                    }
                )
            )
        return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--mode", choices=["vector", "hybrid", "hybrid-bigram"], default="vector")
    args = parser.parse_args()
    if args.mode == "vector":
        retriever: Retriever | HybridRetriever = Retriever.from_settings()
    else:
        retriever = HybridRetriever.from_settings(
            "bigram" if args.mode.endswith("bigram") else "jieba"
        )
    for hit in retriever.search(args.question, args.k):
        snippet = hit.text.replace("\n", " ")[:40]
        print(
            f"{hit.rank}. {hit.score:.3f}  {hit.law_short_name} 第 {hit.article_no} 條"
            f"  [{hit.chunk_id}]  {snippet}…"
        )


if __name__ == "__main__":
    main()
