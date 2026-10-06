from pathlib import Path

import chromadb
import pytest

from app.core.embedder import CachedEmbedder, InputType
from app.pipeline.retrieve import Retriever


class AxisEmbedder:
    """文字裡有「甲」就偏向 x 軸、有「乙」偏向 y 軸，讓距離可預測。"""

    model = "axis-1"

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], InputType]] = []

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        self.calls.append((texts, input_type))
        return [[1.0 + t.count("甲") * 3, 1.0 + t.count("乙") * 3] for t in texts]


def make_collection(tmp_path: Path, rows: list[tuple[str, str, str, str]]) -> chromadb.Collection:
    """rows: (chunk_id, pcode, article_no, text)"""
    embedder = AxisEmbedder()
    collection = chromadb.PersistentClient(path=str(tmp_path / "idx")).create_collection(
        "test_chunks", metadata={"hnsw:space": "cosine"}
    )
    collection.add(
        ids=[r[0] for r in rows],
        embeddings=embedder.embed([r[3] for r in rows], "document"),  # type: ignore[arg-type]
        documents=[r[3] for r in rows],
        metadatas=[{"pcode": r[1], "article_no": r[2], "law_short_name": "測試"} for r in rows],
    )
    return collection


ROWS = [
    ("T:1", "T", "1", "甲甲甲"),
    ("T:2-p1", "T", "2", "甲甲甲甲"),  # 第 2 條被切成兩塊，兩塊都很像「甲」
    ("T:2-p2", "T", "2", "甲甲甲"),
    ("T:3", "T", "3", "乙乙乙"),
    ("T:4", "T", "4", "甲乙"),
]


def test_results_are_ranked_by_score(tmp_path: Path) -> None:
    retriever = Retriever(make_collection(tmp_path, ROWS), AxisEmbedder())
    hits = retriever.search("甲甲", k=5)
    assert [h.rank for h in hits] == [1, 2, 3, 4]
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert hits[-1].article_id == "T:3"  # 完全是「乙」的最不像
    assert all(0.0 <= h.score <= 1.0 for h in hits)


def test_chunks_of_same_article_are_deduplicated(tmp_path: Path) -> None:
    hits = Retriever(make_collection(tmp_path, ROWS), AxisEmbedder()).search("甲甲", k=5)
    article_ids = [h.article_id for h in hits]
    assert len(article_ids) == len(set(article_ids))
    assert article_ids.count("T:2") == 1


def test_k_limits_results_and_oversampling_fills_after_dedup(tmp_path: Path) -> None:
    retriever = Retriever(make_collection(tmp_path, ROWS), AxisEmbedder())
    hits = retriever.search("甲甲", k=3)
    assert len(hits) == 3  # 即使前幾名有同一條的兩塊，去重後仍補滿 k 條


def test_query_uses_query_input_type(tmp_path: Path) -> None:
    embedder = AxisEmbedder()
    Retriever(make_collection(tmp_path, ROWS), embedder).search("甲")
    assert embedder.calls[-1][1] == "query"


def test_score_is_one_minus_cosine_distance(tmp_path: Path) -> None:
    hits = Retriever(make_collection(tmp_path, ROWS), AxisEmbedder()).search("甲甲甲", k=1)
    assert hits[0].score == pytest.approx(1.0, abs=1e-3)  # 方向相同的向量


def test_cached_embedder_only_calls_api_for_new_texts(tmp_path: Path) -> None:
    inner = AxisEmbedder()
    path = tmp_path / "cache" / "q.json"
    cached = CachedEmbedder(inner, path)
    first = cached.embed(["甲", "乙"], "query")
    assert cached.embed(["甲", "乙"], "query") == first
    assert len(inner.calls) == 1  # 第二次全部命中快取
    cached.embed(["甲", "丙"], "query")
    assert inner.calls[-1][0] == ["丙"]  # 只送沒看過的
    # 重新載入檔案後仍有快取
    reloaded = CachedEmbedder(AxisEmbedder(), path)
    reloaded.embed(["甲"], "query")
    assert reloaded._inner.calls == []  # type: ignore[attr-defined]
    # input_type 不同要分開
    inner.calls.clear()
    cached.embed(["甲"], "document")
    assert len(inner.calls) == 1
