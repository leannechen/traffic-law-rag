from typing import Literal

from pydantic import BaseModel


class LawMeta(BaseModel):
    pcode: str
    law_name: str
    law_short_name: str
    law_level: Literal["法律", "命令"]
    article_count: int
    chunk_count: int
    amended_date: str


class IndexMeta(BaseModel):
    data_version: str
    built_at: str
    embedding_model: str
    chunk_count: int
    laws: list[LawMeta]
