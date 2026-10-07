"""SSE 事件（spec 5.3）。共用外框：{type, run_id, ts, data}。

線上格式：每個事件一段 `event: {type}\\ndata: {外框 JSON}\\n\\n`。
前端只需解析 data 這一行的 JSON，再依 type 區分（discriminated union）。
"""

import json
import time
from typing import Annotated, Literal

from pydantic import BaseModel, Field

StepName = Literal["rewrite", "retrieve", "rerank", "gate", "generate", "validate"]


class _Envelope(BaseModel):
    run_id: str
    ts: int = Field(default_factory=lambda: int(time.time() * 1000))  # 毫秒


class RunStartedData(BaseModel):
    question: str


class StepStartedData(BaseModel):
    step: StepName


class StepCompletedData(BaseModel):
    step: StepName
    duration_ms: int
    summary: str  # 給畫面顯示的一行短文字


class RewriteResultData(BaseModel):
    queries: list[str]


class RetrievalItem(BaseModel):
    chunk_id: str
    pcode: str
    law_name: str
    law_short_name: str
    article_no: str
    score: float  # 餘弦相似度
    snippet: str
    rank: int
    source_url: str
    amended_date: str


class RetrievalResultsData(BaseModel):
    items: list[RetrievalItem]


class AnswerDeltaData(BaseModel):
    text: str


class AnswerCitationData(BaseModel):
    marker: str  # 文字中的原樣標記，例如 "[[K0040012:53]]"
    chunk_id: str  # 被引用的條（article_id）；去掉 -p{n} 即與 retrieval.results 的條對應


class AnswerRefusedData(BaseModel):
    reason: Literal["low_relevance", "out_of_scope"]
    top_score: float | None
    threshold: float


class ValidateResultData(BaseModel):
    valid: list[str]
    invalid: list[str]


class RunCompletedData(BaseModel):
    total_ms: int


class ErrorData(BaseModel):
    code: Literal["llm_error", "embedding_error", "internal_error"]
    message: str


class RunStarted(_Envelope):
    type: Literal["run.started"] = "run.started"
    data: RunStartedData


class StepStarted(_Envelope):
    type: Literal["step.started"] = "step.started"
    data: StepStartedData


class StepCompleted(_Envelope):
    type: Literal["step.completed"] = "step.completed"
    data: StepCompletedData


class RewriteResult(_Envelope):
    type: Literal["rewrite.result"] = "rewrite.result"
    data: RewriteResultData


class RetrievalResults(_Envelope):
    type: Literal["retrieval.results"] = "retrieval.results"
    data: RetrievalResultsData


class AnswerDelta(_Envelope):
    type: Literal["answer.delta"] = "answer.delta"
    data: AnswerDeltaData


class AnswerCitation(_Envelope):
    type: Literal["answer.citation"] = "answer.citation"
    data: AnswerCitationData


class AnswerRefused(_Envelope):
    type: Literal["answer.refused"] = "answer.refused"
    data: AnswerRefusedData


class ValidateResult(_Envelope):
    type: Literal["validate.result"] = "validate.result"
    data: ValidateResultData


class RunCompleted(_Envelope):
    type: Literal["run.completed"] = "run.completed"
    data: RunCompletedData


class ErrorEvent(_Envelope):
    type: Literal["error"] = "error"
    data: ErrorData


Event = Annotated[
    RunStarted
    | StepStarted
    | StepCompleted
    | RewriteResult
    | RetrievalResults
    | AnswerDelta
    | AnswerCitation
    | AnswerRefused
    | ValidateResult
    | RunCompleted
    | ErrorEvent,
    Field(discriminator="type"),
]


def to_sse(event: _Envelope) -> str:
    """一個事件的線上格式。ensure_ascii=False 讓 curl 看到的是中文而不是 \\uXXXX。"""
    payload = json.dumps(event.model_dump(), ensure_ascii=False)
    return f"event: {event.type}\ndata: {payload}\n\n"  # type: ignore[attr-defined]
