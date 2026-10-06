import shutil
from pathlib import Path

import chromadb
import pytest
from fastapi.testclient import TestClient

from app.api import meta as meta_api
from app.core.config import Settings
from app.core.embedder import InputType
from app.ingestion import parse
from app.ingestion.build_index import COLLECTION, META_FILE, build_index
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


class FakeEmbedder:
    model = "fake-1"

    def __init__(self) -> None:
        self.calls: list[tuple[int, InputType]] = []

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        self.calls.append((len(texts), input_type))
        return [[float(len(t) % 7), 1.0, float(i)] for i, t in enumerate(texts)]


@pytest.fixture
def processed(tmp_path: Path) -> Path:
    """用 fixture 的真實片段跑 parse，得到一份小的 data/processed。"""
    import zipfile

    from app.ingestion.targets import Target

    targets = {
        "K0040012": Target(pcode="K0040012", short_name="道交處罰條例", priority="must"),
        "D0080090": Target(pcode="D0080090", short_name="事故處理辦法", priority="must"),
    }
    out = tmp_path / "processed"
    out.mkdir()
    for xml in ("law.xml", "order.xml"):
        zip_path = tmp_path / f"{xml}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(FIXTURES / xml, arcname="data.xml")
        for law, _ in parse.iter_target_laws(zip_path, targets, "2026-10-05"):
            (out / f"{law.pcode}.json").write_text(law.model_dump_json(), encoding="utf-8")
    return out


def test_build_index_writes_chroma_and_meta(processed: Path, tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    embedder = FakeEmbedder()
    chunks, meta = build_index(processed, index_dir, embedder)

    assert embedder.calls == [(len(chunks), "document")]
    assert meta.data_version == "2026-10-05"
    assert meta.chunk_count == len(chunks) == sum(law.chunk_count for law in meta.laws)
    assert (index_dir / META_FILE).exists()

    collection = chromadb.PersistentClient(path=str(index_dir)).get_collection(COLLECTION)
    assert collection.count() == len(chunks)
    got = collection.get(ids=["K0040012:53"], include=["documents", "metadatas"])
    assert got["documents"] and "闖紅燈" in got["documents"][0]
    assert got["metadatas"] and got["metadatas"][0]["law_short_name"] == "道交處罰條例"
    assert "paragraph_no" not in got["metadatas"][0]  # None 不寫入


def test_rebuild_is_identical(processed: Path, tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    first, _ = build_index(processed, index_dir, FakeEmbedder())
    second, _ = build_index(processed, index_dir, FakeEmbedder())
    assert first == second
    collection = chromadb.PersistentClient(path=str(index_dir)).get_collection(COLLECTION)
    assert collection.count() == len(second)  # 重建不會越積越多
    ids = collection.get()["ids"]
    assert len(ids) == len(set(ids))


def test_meta_endpoint(processed: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    index_dir = tmp_path / "index"
    build_index(processed, index_dir, FakeEmbedder())
    settings = Settings(data_dir=tmp_path)
    (tmp_path / "index").mkdir(exist_ok=True)
    monkeypatch.setattr(meta_api, "get_settings", lambda: settings)

    res = TestClient(app).get("/api/meta")
    assert res.status_code == 200
    body = res.json()
    assert body["data_version"] == "2026-10-05"
    assert {law["pcode"] for law in body["laws"]} == {"K0040012", "D0080090"}


def test_meta_endpoint_without_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(meta_api, "get_settings", lambda: Settings(data_dir=tmp_path))
    assert TestClient(app).get("/api/meta").status_code == 503
    shutil.rmtree(tmp_path, ignore_errors=True)
