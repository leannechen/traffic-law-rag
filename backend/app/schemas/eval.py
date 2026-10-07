"""評估頁用的資料（GET /api/eval/latest）。由 eval/results 的原始結果整理而來。"""

from typing import Literal

from pydantic import BaseModel

Retrieval = Literal["hit", "partial", "miss", "na"]
Citation = Literal["ok", "wrong", "refused_ok", "answered_out_of_scope", "false_refusal"]
Numbers = Literal["ok", "mismatch", "na"]


class EvalMetrics(BaseModel):
    recall_at_5: float
    mrr: float
    citation_accuracy: float
    number_accuracy: float | None  # 沒有任何數字可比對時為 None
    refusal_accuracy: float


class EvalCounts(BaseModel):
    verified: int
    answerable: int
    out_of_scope: int


class EvalRetrievedItem(BaseModel):
    article_id: str
    score: float | None


class EvalRow(BaseModel):
    id: str
    question: str
    category: str
    should_refuse: bool
    expected: list[str]  # 標準答案（條 id）
    retrieved: list[EvalRetrievedItem]  # 系統檢索前 5 條
    retrieval: Retrieval
    first_hit_rank: int | None
    citation: Citation
    numbers: Numbers
    fact_amounts_expected: int | None
    fact_amounts_found: int | None


class EvalReport(BaseModel):
    name: str
    evaluated_at: str
    data_version: str
    counts: EvalCounts
    metrics: EvalMetrics
    questions: list[EvalRow]
