"""以「條」為單位取回整條條文（依項切成多塊的條文會把各塊串回去）。"""

import re
from typing import Any, Protocol

from pydantic import BaseModel

from app.schemas.chunk import ChunkDetail

_PART_RE = re.compile(r"-p(\d+)$")


class ArticleText(BaseModel):
    article_id: str  # "{pcode}:{article_no}"
    law_short_name: str
    article_no: str
    text: str  # 整條原文


class ArticleSource(Protocol):
    def get(self, article_id: str) -> ArticleText | None: ...


class ChromaArticleSource:
    def __init__(self, collection: Any) -> None:
        self._collection = collection
        self._cache: dict[str, ArticleText | None] = {}

    def get(self, article_id: str) -> ArticleText | None:
        if article_id in self._cache:
            return self._cache[article_id]
        if ":" not in article_id:
            return None
        pcode, article_no = article_id.split(":", 1)
        got = self._collection.get(
            where={"$and": [{"pcode": pcode}, {"article_no": article_no}]},
            include=["documents", "metadatas"],
        )
        rows = list(zip(got["ids"], got["documents"] or [], got["metadatas"] or [], strict=True))
        result: ArticleText | None = None
        if rows:

            def order(row: tuple[str, str, Any]) -> int:
                m = _PART_RE.search(row[0])
                return int(m.group(1)) if m else 0

            rows.sort(key=order)
            result = ArticleText(
                article_id=article_id,
                law_short_name=str(rows[0][2]["law_short_name"]),
                article_no=article_no,
                text="\n".join(r[1] for r in rows),
            )
        self._cache[article_id] = result
        return result


class ChromaChunkStore:
    """依 chunk_id 取回單一 chunk 的欄位，加上整條全文。"""

    def __init__(self, collection: Any, articles: ArticleSource) -> None:
        self._collection = collection
        self._articles = articles

    def get(self, chunk_id: str) -> ChunkDetail | None:
        got = self._collection.get(ids=[chunk_id], include=["documents", "metadatas"])
        if got["ids"]:
            text, meta = got["documents"][0], got["metadatas"][0]
        else:
            # 引用事件裡的 id 是「條」，依項切分的條文沒有同名的 chunk：改取該條的第一塊
            if _PART_RE.search(chunk_id):
                return None  # 指名了不存在的項（例如 -p9），不要退回第一塊
            first = self._first_chunk(chunk_id)
            if first is None:
                return None
            text, meta = first
        article_id = f"{meta['pcode']}:{meta['article_no']}"
        article = self._articles.get(article_id)
        if article is None:
            return None
        return ChunkDetail(
            chunk_id=chunk_id,
            article_id=article_id,
            pcode=str(meta["pcode"]),
            law_name=str(meta["law_name"]),
            law_short_name=str(meta["law_short_name"]),
            law_level=meta["law_level"],
            article_no=str(meta["article_no"]),
            paragraph_no=meta.get("paragraph_no"),
            chapter=meta.get("chapter"),
            text=text,
            source_url=str(meta["source_url"]),
            amended_date=str(meta["amended_date"]),
            data_version=str(meta["data_version"]),
            article_text=article.text,
        )

    def _first_chunk(self, article_id: str) -> tuple[str, Any] | None:
        if ":" not in article_id:
            return None
        pcode, article_no = article_id.split(":", 1)
        got = self._collection.get(
            where={"$and": [{"pcode": pcode}, {"article_no": article_no}]},
            include=["documents", "metadatas"],
        )
        rows = list(zip(got["ids"], got["documents"] or [], got["metadatas"] or [], strict=True))
        if not rows:
            return None
        rows.sort(key=lambda r: int(m.group(1)) if (m := _PART_RE.search(r[0])) else 0)
        return rows[0][1], rows[0][2]
