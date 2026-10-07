from collections.abc import Callable, Generator
from typing import Any

from app.core.llm import Effort, LLMResponse
from app.pipeline.articles import ArticleText
from app.schemas.retrieval import RetrievedChunk


class FakeLLM:
    """依 user prompt 內容決定回應；記錄每次呼叫。"""

    model = "fake-llm"

    def __init__(
        self,
        respond: Callable[[str, str], str] | str,
        *,
        refused: bool = False,
        chunk_size: int = 4,
        fail_after: int | None = None,
        error: Exception | None = None,
    ) -> None:
        self._respond = respond
        self._refused = refused
        self._chunk_size = chunk_size  # 串流時每段幾個字元（刻意切得很碎，測標記跨段）
        self._fail_after = fail_after  # 串流送出幾段後丟出 error
        self._error = error
        self.calls: list[dict[str, Any]] = []
        self.closed = False

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

    def stream(
        self, *, system: str, user: str, max_tokens: int, effort: Effort
    ) -> Generator[str | LLMResponse, None, None]:
        return _stream(self, system, user, effort)


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


def _stream(
    self: FakeLLM, system: str, user: str, effort: Effort
) -> Generator[str | LLMResponse, None, None]:
    self.calls.append({"system": system, "user": user, "effort": effort, "stream": True})
    text = self._respond if isinstance(self._respond, str) else self._respond(system, user)
    try:
        step = self._chunk_size
        for sent, i in enumerate(range(0, len(text), step)):
            if self._fail_after is not None and sent >= self._fail_after:
                raise self._error or RuntimeError("boom")
            yield text[i : i + step]
        yield LLMResponse(
            text=text, model=self.model, refused=self._refused, input_tokens=10, output_tokens=5
        )
    except GeneratorExit:
        self.closed = True  # 呼叫端提前關閉（例如使用者斷線）
        raise


class FakeSearcher:
    """依查詢字串回傳預先設定的結果。"""

    def __init__(self, results: dict[str, list[RetrievedChunk]]) -> None:
        self._results = results
        self.queries: list[str] = []

    def search(self, question: str, k: int = 5) -> list[RetrievedChunk]:
        self.queries.append(question)
        hits = self._results.get(question, [])
        return [h.model_copy(update={"rank": i}) for i, h in enumerate(hits[:k], start=1)]


class FakeArticles:
    """article_id → 整條原文；沒設定的條退回 None（pipeline 會改用檢索到的那一塊）。"""

    def __init__(self, texts: dict[str, str] | None = None) -> None:
        self._texts = texts or {}

    def get(self, article_id: str) -> ArticleText | None:
        if article_id not in self._texts:
            return None
        pcode, no = article_id.split(":")
        return ArticleText(
            article_id=article_id,
            law_short_name="測試法",
            article_no=no,
            text=self._texts[article_id],
        )
