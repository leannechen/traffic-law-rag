"""以「條」為單位取回整條條文（依項切成多塊的條文會把各塊串回去）。"""

import re
from typing import Any, Protocol

from pydantic import BaseModel

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
