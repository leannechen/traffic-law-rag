from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    rank: int  # 1 起算
    score: float  # 餘弦相似度（1 − 距離）；只在同一模型、同一份索引內可比較
    chunk_id: str
    article_id: str  # "{pcode}:{article_no}"，UI 以條為單位
    pcode: str
    law_short_name: str
    article_no: str
    text: str
