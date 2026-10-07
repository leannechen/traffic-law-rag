from pathlib import Path

import chromadb

from app.pipeline.articles import ChromaArticleSource


def make_source(tmp_path: Path, rows: list[tuple[str, str, str]]) -> ChromaArticleSource:
    """rows: (chunk_id, article_no, text)"""
    collection = chromadb.PersistentClient(path=str(tmp_path / "idx")).create_collection(
        "test_chunks", metadata={"hnsw:space": "cosine"}
    )
    collection.add(
        ids=[r[0] for r in rows],
        embeddings=[[1.0, 0.0]] * len(rows),  # type: ignore[arg-type]
        documents=[r[2] for r in rows],
        metadatas=[{"pcode": "T", "article_no": r[1], "law_short_name": "測"} for r in rows],
    )
    return ChromaArticleSource(collection)


def test_whole_article_is_joined_in_chunk_order(tmp_path: Path) -> None:
    # 故意用 p10 驗證依數字而不是字串排序（字串排序會是 p1、p10、p2）
    rows = [(f"T:35-p{i}", "35", f"第{i}塊") for i in (2, 10, 1, 3)]
    rows.append(("T:36", "36", "別條"))
    source = make_source(tmp_path, rows)
    article = source.get("T:35")
    assert article is not None
    assert article.text == "第1塊\n第2塊\n第3塊\n第10塊"
    assert article.law_short_name == "測" and article.article_no == "35"


def test_unsplit_article_returns_its_single_chunk(tmp_path: Path) -> None:
    source = make_source(tmp_path, [("T:53", "53", "原文"), ("T:53-1", "53-1", "另一條")])
    article = source.get("T:53")
    assert article is not None and article.text == "原文"  # 53 不會混進 53-1


def test_unknown_article_returns_none(tmp_path: Path) -> None:
    assert make_source(tmp_path, [("T:1", "1", "x")]).get("T:999") is None
