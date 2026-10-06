"""切 chunk、算 embedding、寫入 Chroma（data/index/）。

    uv run python -m app.ingestion.build_index

索引目錄內另有 index_meta.json，記錄 data_version 等資訊，/api/meta 由此讀出。
"""

import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import chromadb

from app.core.config import get_settings
from app.core.embedder import Embedder, VoyageEmbedder
from app.ingestion.chunk import MAX_CHARS, check_chunks, chunk_all, load_processed
from app.schemas.law import LawChunk, ParsedLaw
from app.schemas.meta import IndexMeta, LawMeta

COLLECTION = "law_chunks"
META_FILE = "index_meta.json"


def chunk_metadata(chunk: LawChunk) -> dict[str, str | int]:
    """Chroma 的 metadata 不接受 None，值為 None 的欄位省略。"""
    data = chunk.model_dump(exclude={"text", "embed_text"})
    return {k: v for k, v in data.items() if v is not None}


def build_meta(
    laws: list[ParsedLaw], chunks: list[LawChunk], model: str, built_at: str
) -> IndexMeta:
    per_law = Counter(c.pcode for c in chunks)
    return IndexMeta(
        data_version=laws[0].data_version,
        built_at=built_at,
        embedding_model=model,
        chunk_count=len(chunks),
        laws=[
            LawMeta(
                pcode=law.pcode,
                law_name=law.law_name,
                law_short_name=law.law_short_name,
                law_level=law.law_level,
                article_count=len(law.articles),
                chunk_count=per_law[law.pcode],
                amended_date=law.amended_date,
            )
            for law in laws
        ],
    )


def build_index(
    processed_dir: Path, index_dir: Path, embedder: Embedder
) -> tuple[list[LawChunk], IndexMeta]:
    laws = load_processed(processed_dir)
    if not laws:
        raise SystemExit(f"{processed_dir} 沒有資料，先執行 python -m app.ingestion.parse")
    if len({law.data_version for law in laws}) != 1:
        raise SystemExit("data/processed 內的 data_version 不一致，請重跑 parse")
    chunks = chunk_all(laws)
    check_chunks(chunks)
    vectors = embedder.embed([c.embed_text for c in chunks], "document")
    if len(vectors) != len(chunks):
        raise RuntimeError("embedding 數量與 chunk 數量不符")

    index_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_dir))
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)  # 每次整個重建，不做增量
    collection = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    collection.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=vectors,  # type: ignore[arg-type]
        documents=[c.text for c in chunks],
        metadatas=[chunk_metadata(c) for c in chunks],
    )
    meta = build_meta(laws, chunks, embedder.model, datetime.now(UTC).isoformat(timespec="seconds"))
    (index_dir / META_FILE).write_text(meta.model_dump_json(indent=2), encoding="utf-8")
    return chunks, meta


def print_stats(chunks: list[LawChunk], meta: IndexMeta) -> None:
    print(f"data_version = {meta.data_version}  model = {meta.embedding_model}")
    print(f"{'法規':14} {'條':>4} {'chunk':>6} {'平均字數':>8} {'最大':>5}")
    for law in meta.laws:
        lengths = [len(c.text) for c in chunks if c.pcode == law.pcode]
        print(
            f"{law.law_short_name:14} {law.article_count:>4} {law.chunk_count:>6} "
            f"{statistics.mean(lengths):>8.0f} {max(lengths):>5}"
        )
    lengths = [len(c.text) for c in chunks]
    print(
        f"{'合計':14} {sum(m.article_count for m in meta.laws):>4} {len(chunks):>6} "
        f"{statistics.mean(lengths):>8.0f} {max(lengths):>5}"
    )
    split = sorted({c.article_id for c in chunks if c.paragraph_no is not None})
    print(f"\n被切成多塊的條文（原文 > {MAX_CHARS} 字）共 {len(split)} 條：")
    for article_id in split:
        parts = [c for c in chunks if c.article_id == article_id]
        print(f"  {article_id:18} → {len(parts)} 塊 {[len(c.text) for c in parts]}")


def main() -> None:
    settings = get_settings()
    embedder = VoyageEmbedder(settings.voyage_api_key, settings.embedding_model)
    chunks, meta = build_index(settings.data_dir / "processed", settings.index_dir, embedder)
    print_stats(chunks, meta)


if __name__ == "__main__":
    main()
