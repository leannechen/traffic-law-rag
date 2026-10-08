"""串流版問答：rewrite → retrieve → gate → generate → validate，每一步都送事件（spec 5.3）。

Step 5 的 answer_question 是同一條流程的非串流版（評估用）；這裡的測試會驗證兩者結果一致。
"""

import logging
import time
import uuid
from collections.abc import Generator, Iterator
from dataclasses import dataclass

from app.core.embedder import EmbeddingError
from app.core.llm import LLMClient, LLMError, LLMResponse
from app.pipeline.answer import CONTEXT_K, Searcher, build_context, retrieve_multi
from app.pipeline.articles import ArticleSource
from app.pipeline.gate import check_gate
from app.pipeline.generate import MAX_TOKENS, build_user_prompt, load_prompt
from app.pipeline.rewrite import rewrite_question
from app.pipeline.stream_parser import Citation, StreamParser, Text
from app.pipeline.validate import check_numbers, validate_citations
from app.schemas.events import (
    AnswerCitation,
    AnswerCitationData,
    AnswerDelta,
    AnswerDeltaData,
    AnswerRefused,
    AnswerRefusedData,
    ErrorData,
    ErrorEvent,
    Event,
    RetrievalItem,
    RetrievalResults,
    RetrievalResultsData,
    RewriteResult,
    RewriteResultData,
    RunCompleted,
    RunCompletedData,
    RunStarted,
    RunStartedData,
    StepCompleted,
    StepCompletedData,
    StepName,
    StepStarted,
    StepStartedData,
    ValidateResult,
    ValidateResultData,
)
from app.schemas.retrieval import RetrievedChunk

log = logging.getLogger("app.ask")
SNIPPET_CHARS = 90


@dataclass
class AskDeps:
    searcher: Searcher
    articles: ArticleSource
    llm: LLMClient
    gate_threshold: float
    rewrite_enabled: bool = False


def _snippet(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= SNIPPET_CHARS else flat[:SNIPPET_CHARS] + "…"


def _item(hit: RetrievedChunk, rank: int) -> RetrievalItem:
    return RetrievalItem(
        chunk_id=hit.chunk_id,
        pcode=hit.pcode,
        law_name=hit.law_name,
        law_short_name=hit.law_short_name,
        article_no=hit.article_no,
        score=hit.vector_score if hit.vector_score is not None else hit.score,
        snippet=_snippet(hit.text),
        rank=rank,
        source_url=hit.source_url,
        amended_date=hit.amended_date,
    )


class _Step:
    """量測一個步驟的耗時，產生 step.started／step.completed。"""

    def __init__(self, run_id: str, name: StepName) -> None:
        self._run_id, self._name = run_id, name
        self._t0 = time.perf_counter()

    def started(self) -> StepStarted:
        self._t0 = time.perf_counter()
        return StepStarted(run_id=self._run_id, data=StepStartedData(step=self._name))

    def completed(self, summary: str) -> StepCompleted:
        ms = int((time.perf_counter() - self._t0) * 1000)
        return StepCompleted(
            run_id=self._run_id,
            data=StepCompletedData(step=self._name, duration_ms=ms, summary=summary),
        )


def run_ask(question: str, deps: AskDeps) -> Generator[Event, None, None]:
    """產生一次問答的所有事件。任何失敗都轉成 error 事件後結束（不丟出例外給 HTTP 層）。"""
    run_id = uuid.uuid4().hex
    t0 = time.perf_counter()
    try:
        yield from _run(question, deps, run_id, t0)
    except GeneratorExit:
        # 呼叫端提早結束（使用者斷線、取消）：不再繼續呼叫模型，只記一筆
        log.info("run=%s 提早結束（%d ms）", run_id, int((time.perf_counter() - t0) * 1000))
        raise
    except LLMError as e:
        log.warning("llm error run=%s: %s", run_id, e)
        yield ErrorEvent(
            run_id=run_id,
            data=ErrorData(code="llm_error", message="產生答案時發生問題，請稍後再試。"),
        )
    except EmbeddingError as e:
        log.warning("embedding error run=%s: %s", run_id, e)
        yield ErrorEvent(
            run_id=run_id,
            data=ErrorData(code="embedding_error", message="檢索條文時發生問題，請稍後再試。"),
        )
    except Exception:
        log.exception("unexpected error run=%s", run_id)
        yield ErrorEvent(
            run_id=run_id,
            data=ErrorData(code="internal_error", message="系統發生錯誤，請稍後再試。"),
        )


def _run(question: str, deps: AskDeps, run_id: str, t0: float) -> Iterator[Event]:
    yield RunStarted(run_id=run_id, data=RunStartedData(question=question))

    # 1. rewrite（關閉時仍送出，讓畫面的五個步驟固定）
    step = _Step(run_id, "rewrite")
    yield step.started()
    if deps.rewrite_enabled:
        queries, _, _ = rewrite_question(deps.llm, question)
        summary = f"{len(queries)} 個查詢"
    else:
        queries, summary = [question], "未啟用"
    yield RewriteResult(run_id=run_id, data=RewriteResultData(queries=queries))
    yield step.completed(summary)

    # 2. retrieve
    step = _Step(run_id, "retrieve")
    yield step.started()
    retrieved = retrieve_multi(deps.searcher, queries)
    shown = retrieved[:CONTEXT_K]
    yield RetrievalResults(
        run_id=run_id,
        data=RetrievalResultsData(items=[_item(h, i) for i, h in enumerate(shown, start=1)]),
    )
    yield step.completed(f"top {len(shown)}")

    # 3. gate（門檻看原始問題的第一名相似度）
    step = _Step(run_id, "gate")
    yield step.started()
    original = retrieved if len(queries) == 1 else deps.searcher.search(question, 1)
    top_score = original[0].vector_score if original else None
    gate = check_gate(top_score, deps.gate_threshold)
    if gate.passed:
        yield step.completed(f"最高 {top_score:.2f} ≥ 門檻 {gate.threshold:.2f}")
    else:
        shown_score = f"{top_score:.2f}" if top_score is not None else "無"
        yield step.completed(f"最高 {shown_score} < 門檻 {gate.threshold:.2f}")
        yield AnswerRefused(
            run_id=run_id,
            data=AnswerRefusedData(
                reason="low_relevance", top_score=top_score, threshold=gate.threshold
            ),
        )
        yield _completed(run_id, t0)
        return

    # 4. generate（串流）
    step = _Step(run_id, "generate")
    yield step.started()
    context = build_context(retrieved, deps.articles)
    parser = StreamParser()
    answer_parts: list[str] = []
    cited: list[str] = []
    final: LLMResponse | None = None

    def convert(items: list[object]) -> Iterator[Event]:
        for item in items:
            if isinstance(item, Text):
                answer_parts.append(item.text)
                yield AnswerDelta(run_id=run_id, data=AnswerDeltaData(text=item.text))
            elif isinstance(item, Citation):
                if item.chunk_id not in cited:
                    cited.append(item.chunk_id)
                yield AnswerCitation(
                    run_id=run_id,
                    data=AnswerCitationData(marker=item.marker, chunk_id=item.chunk_id),
                )

    stream = deps.llm.stream(
        system=load_prompt("generate.md"),
        user=build_user_prompt(question, context),
        max_tokens=MAX_TOKENS,
        effort="medium",
    )
    try:
        for piece in stream:
            if isinstance(piece, LLMResponse):
                final = piece
                continue
            items = parser.feed(piece)
            yield from convert(list(items))
            if parser.refused:
                break  # 已確定是拒答：不必再讀完整個串流（finally 會關閉對模型的串流，停止計費）
        yield from convert(list(parser.finish()))
    finally:
        stream.close()  # 呼叫端提早結束（例如斷線）時，連帶關閉對模型的串流

    if final is not None:  # 只記數字不記問題內容，供估算每次提問的成本
        log.info(
            "usage run=%s model=%s input_tokens=%d output_tokens=%d",
            run_id,
            final.model,
            final.input_tokens,
            final.output_tokens,
        )

    if parser.refused or (final is not None and final.refused):
        yield step.completed("條文不足，模型拒答")
        yield AnswerRefused(
            run_id=run_id,
            data=AnswerRefusedData(
                reason="out_of_scope", top_score=top_score, threshold=gate.threshold
            ),
        )
        yield _completed(run_id, t0)
        return
    if final is not None and final.stop_reason == "max_tokens":
        # 答案被長度上限截斷：不能當成完整答案送出
        log.warning("answer truncated run=%s", run_id)
        yield ErrorEvent(
            run_id=run_id,
            data=ErrorData(
                code="truncated", message="答案太長，被截斷了。請把問題問得更具體一點。"
            ),
        )
        return
    yield step.completed(f"{len(cited)} 個引用")

    # 5. validate
    step = _Step(run_id, "validate")
    yield step.started()
    allowed = {a.article_id for a in context}
    check = validate_citations(cited, allowed)
    yield ValidateResult(
        run_id=run_id, data=ValidateResultData(valid=check.valid, invalid=check.invalid)
    )
    yield step.completed(f"{len(check.valid)} / {len(cited)} 通過")
    numbers = check_numbers(
        "".join(answer_parts), [a.text for a in context if a.article_id in set(check.valid)]
    )
    if numbers.unmatched:  # 不在事件中（spec 的 validate.result 只有引用），記在 log 供追查
        log.warning("run=%s 答案中的數字在引用條文找不到：%s", run_id, numbers.unmatched)
    yield _completed(run_id, t0)


def _completed(run_id: str, t0: float) -> RunCompleted:
    return RunCompleted(
        run_id=run_id, data=RunCompletedData(total_ms=int((time.perf_counter() - t0) * 1000))
    )
