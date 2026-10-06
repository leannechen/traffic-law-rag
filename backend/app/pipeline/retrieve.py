"""向量檢索：問題 → query embedding → Chroma → 以「條」去重的 top-k。

uv run python -m app.pipeline.retrieve "紅燈右轉罰多少"
"""

import argparse
from typing import Any

import chromadb

from app.core.config import get_settings
from app.core.embedder import CachedEmbedder, Embedder, VoyageEmbedder
from app.ingestion.build_index import COLLECTION
from app.schemas.retrieval import RetrievedChunk

# 同一條可能被切成多塊、同時占住前幾名，所以先多取再去重。
OVERFETCH = 3


class Retriever:
    def __init__(self, collection: Any, embedder: Embedder) -> None:
        self._collection = collection
        self._embedder = embedder

    @classmethod
    def from_settings(cls) -> "Retriever":
        settings = get_settings()
        collection = chromadb.PersistentClient(path=str(settings.index_dir)).get_collection(
            COLLECTION
        )
        inner = VoyageEmbedder(settings.voyage_api_key, settings.embedding_model)
        embedder = CachedEmbedder(inner, settings.cache_dir / "query_embeddings.json")
        return cls(collection, embedder)

    def search(self, question: str, k: int = 5) -> list[RetrievedChunk]:
        """回傳最多 k 條（同一條只留最高分的那一塊），依分數由高到低。"""
        (vector,) = self._embedder.embed([question], "query")
        n = min(k * OVERFETCH, self._collection.count())
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
            hits.append(
                RetrievedChunk(
                    rank=len(hits) + 1,
                    score=round(1 - distance, 4),
                    chunk_id=chunk_id,
                    article_id=article_id,
                    pcode=str(meta["pcode"]),
                    law_short_name=str(meta["law_short_name"]),
                    article_no=str(meta["article_no"]),
                    text=doc,
                )
            )
            if len(hits) == k:
                break
        return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()
    for hit in Retriever.from_settings().search(args.question, args.k):
        snippet = hit.text.replace("\n", " ")[:40]
        print(
            f"{hit.rank}. {hit.score:.3f}  {hit.law_short_name} 第 {hit.article_no} 條"
            f"  [{hit.chunk_id}]  {snippet}…"
        )


if __name__ == "__main__":
    main()
