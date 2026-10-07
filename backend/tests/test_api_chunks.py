from collections.abc import Iterator
from pathlib import Path

import chromadb
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_chunk_store
from app.main import app
from app.pipeline.articles import ChromaArticleSource, ChromaChunkStore


def meta(article_no: str, **extra: object) -> dict[str, object]:
    return {
        "pcode": "K0040012",
        "article_no": article_no,
        "law_name": "道路交通管理處罰條例",
        "law_short_name": "道交處罰條例",
        "law_level": "法律",
        "chapter": "第 二 章 汽車",
        "source_url": f"https://example.test/{article_no}",
        "amended_date": "20260817",
        "data_version": "2026-10-05",
        **extra,
    }


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    collection = chromadb.PersistentClient(path=str(tmp_path / "idx")).create_collection(
        "test_chunks", metadata={"hnsw:space": "cosine"}
    )
    rows = [
        ("K0040012:53", "闖紅燈者處罰鍰。", meta("53")),
        ("K0040012:35-p1", "前半：酒駕罰鍰。", meta("35", paragraph_no=1)),
        ("K0040012:35-p2", "後半：累犯加重。", meta("35", paragraph_no=4)),
        ("K0040012:53-1", "捷運共用路口。", meta("53-1")),
    ]
    collection.add(
        ids=[r[0] for r in rows],
        embeddings=[[1.0, 0.0]] * len(rows),  # type: ignore[arg-type]
        documents=[r[1] for r in rows],
        metadatas=[r[2] for r in rows],  # type: ignore[misc]
    )
    store = ChromaChunkStore(collection, ChromaArticleSource(collection))
    app.dependency_overrides[get_chunk_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_unsplit_article_returns_fields_and_article_text(client: TestClient) -> None:
    body = client.get("/api/chunks/K0040012:53").json()
    assert body["chunk_id"] == "K0040012:53" and body["article_id"] == "K0040012:53"
    assert body["law_short_name"] == "道交處罰條例" and body["law_level"] == "法律"
    assert body["text"] == body["article_text"] == "闖紅燈者處罰鍰。"
    assert body["paragraph_no"] is None and body["source_url"].endswith("/53")


def test_split_chunk_returns_the_whole_article_text(client: TestClient) -> None:
    """spec 驗收：依項切分的 chunk 取回的 article_text 是整條條文。"""
    body = client.get("/api/chunks/K0040012:35-p2").json()
    assert body["text"] == "後半：累犯加重。"  # 這個 chunk 自己的原文
    assert body["article_text"] == "前半：酒駕罰鍰。\n後半：累犯加重。"  # 整條
    assert body["article_id"] == "K0040012:35" and body["paragraph_no"] == 4


def test_article_id_of_a_split_article_resolves_via_its_first_chunk(client: TestClient) -> None:
    # 引用事件裡的 id 是「條」；依項切分的條文沒有同名的 chunk
    body = client.get("/api/chunks/K0040012:35").json()
    assert body["chunk_id"] == "K0040012:35"
    assert body["article_text"] == "前半：酒駕罰鍰。\n後半：累犯加重。"


def test_article_with_dash_number_is_not_confused_with_its_neighbour(client: TestClient) -> None:
    assert client.get("/api/chunks/K0040012:53-1").json()["article_text"] == "捷運共用路口。"
    assert client.get("/api/chunks/K0040012:53").json()["article_text"] == "闖紅燈者處罰鍰。"


def test_unknown_chunk_is_404(client: TestClient) -> None:
    assert client.get("/api/chunks/K0040012:999").status_code == 404
    assert client.get("/api/chunks/K0040012:999-p2").status_code == 404
