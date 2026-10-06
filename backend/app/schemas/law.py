from typing import Literal

from pydantic import BaseModel


class ParsedArticle(BaseModel):
    article_no: str  # "53"、"53-1"
    chapter: str | None
    text: str  # 條文原文（項以換行分隔）
    paragraphs: list[str]  # 依「項」切分；款留在所屬項內


class ParsedLaw(BaseModel):
    pcode: str
    law_name: str
    law_short_name: str
    law_level: Literal["法律", "命令"]
    amended_date: str  # 最新異動日期，YYYYMMDD
    source_update_date: str  # 資料集 XML 標示的更新時間
    data_version: str  # 資料下載日期 YYYY-MM-DD
    articles: list[ParsedArticle]


class LawChunk(BaseModel):
    chunk_id: str  # "{pcode}:{article_no}" 或 "{pcode}:{article_no}-p{n}"（n 為 chunk 序號）
    pcode: str
    law_name: str
    law_short_name: str
    law_level: Literal["法律", "命令"]
    article_no: str
    paragraph_no: int | None  # 這個 chunk 從第幾項開始；整條一個 chunk 時為 None
    chapter: str | None
    text: str
    embed_text: str
    source_url: str
    amended_date: str
    data_version: str

    @property
    def article_id(self) -> str:
        return f"{self.pcode}:{self.article_no}"
