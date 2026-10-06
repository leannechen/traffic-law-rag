from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    rank: int  # 1 起算
    score: float  # 向量檢索：餘弦相似度（1 − 距離）；hybrid：RRF 分數。兩者不可互比
    vector_score: float | None = (
        None  # 餘弦相似度；向量檢索時等於 score，hybrid 時另外保留（拒答門檻用）
    )
    chunk_id: str
    article_id: str  # "{pcode}:{article_no}"，UI 以條為單位
    pcode: str
    law_short_name: str
    article_no: str
    text: str
