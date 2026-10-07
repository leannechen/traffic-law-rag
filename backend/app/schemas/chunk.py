from typing import Literal

from pydantic import BaseModel


class ChunkDetail(BaseModel):
    chunk_id: str
    article_id: str
    pcode: str
    law_name: str
    law_short_name: str
    law_level: Literal["法律", "命令"]
    article_no: str
    paragraph_no: int | None = None
    chapter: str | None = None
    text: str  # 這個 chunk 的原文
    source_url: str
    amended_date: str
    data_version: str
    article_text: str  # 所屬條文的整條全文（依項切分時為各項合併）
