from collections.abc import Callable
from typing import Any

from app.core.llm import Effort, LLMResponse
from app.schemas.retrieval import RetrievedChunk


class FakeLLM:
    """依 user prompt 內容決定回應；記錄每次呼叫。"""

    model = "fake-llm"

    def __init__(self, respond: Callable[[str, str], str] | str, *, refused: bool = False) -> None:
        self._respond = respond
        self._refused = refused
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: Effort,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {"system": system, "user": user, "effort": effort, "json_schema": json_schema}
        )
        text = self._respond if isinstance(self._respond, str) else self._respond(system, user)
        return LLMResponse(
            text=text, model=self.model, refused=self._refused, input_tokens=10, output_tokens=5
        )


def chunk(
    chunk_id: str, text: str, score: float = 0.7, *, law: str = "測試法", rank: int = 1
) -> RetrievedChunk:
    pcode, rest = chunk_id.split(":")
    return RetrievedChunk(
        rank=rank,
        score=score,
        vector_score=score,
        chunk_id=chunk_id,
        article_id=f"{pcode}:{rest.split('-p')[0]}",
        pcode=pcode,
        law_short_name=law,
        article_no=rest.split("-p")[0],
        text=text,
    )


class FakeSearcher:
    """依查詢字串回傳預先設定的結果。"""

    def __init__(self, results: dict[str, list[RetrievedChunk]]) -> None:
        self._results = results
        self.queries: list[str] = []

    def search(self, question: str, k: int = 5) -> list[RetrievedChunk]:
        self.queries.append(question)
        hits = self._results.get(question, [])
        return [h.model_copy(update={"rank": i}) for i, h in enumerate(hits[:k], start=1)]
