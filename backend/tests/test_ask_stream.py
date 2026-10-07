from typing import Any

import pytest
from pydantic import TypeAdapter

from app.core.embedder import EmbeddingError
from app.core.llm import LLMError
from app.pipeline.answer import answer_question
from app.pipeline.ask_stream import AskDeps, run_ask
from app.schemas.events import Event
from app.schemas.retrieval import RetrievedChunk
from tests.fakes import FakeArticles, FakeLLM, FakeSearcher, chunk

ANSWER = "紅燈右轉罰六百元以上一千八百元以下[[K:53]]。"
EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)


def hit(chunk_id: str, text: str, score: float, rank: int = 1) -> RetrievedChunk:
    return chunk(chunk_id, text, score, law="道交處罰條例", rank=rank).model_copy(
        update={
            "law_name": "道路交通管理處罰條例",
            "source_url": "https://example.test/x",
            "amended_date": "20260817",
        }
    )


def make_deps(
    llm: FakeLLM,
    *,
    score: float = 0.72,
    rewrite: bool = False,
    searcher: Any = None,
) -> AskDeps:
    results = {
        "紅燈右轉？": [
            hit("K:53", "處新臺幣六百元以上一千八百元以下罰鍰。", score),
            hit("K:58", "處新臺幣六百元以上一千二百元以下罰鍰。", 0.6),
        ]
    }
    return AskDeps(
        searcher=searcher or FakeSearcher(results),
        articles=FakeArticles(),
        llm=llm,
        gate_threshold=0.40,
        rewrite_enabled=rewrite,
    )


def collect(question: str, deps: AskDeps) -> list[Any]:
    return list(run_ask(question, deps))


def types(events: list[Any], *, collapse: bool = True) -> list[str]:
    out: list[str] = []
    for e in events:
        if collapse and e.type == "answer.delta" and out and out[-1] == "answer.delta":
            continue
        out.append(e.type)
    return out


def test_normal_answer_event_order() -> None:
    events = collect("紅燈右轉？", make_deps(FakeLLM(ANSWER)))
    assert types(events) == [
        "run.started",
        "step.started", "rewrite.result", "step.completed",  # rewrite
        "step.started", "retrieval.results", "step.completed",  # retrieve
        "step.started", "step.completed",  # gate
        "step.started", "answer.delta", "answer.citation", "answer.delta",
        "step.completed",  # generate
        "step.started", "validate.result", "step.completed",  # validate
        "run.completed",
    ]  # fmt: skip


def test_steps_are_reported_in_the_documented_order_with_matching_pairs() -> None:
    events = collect("紅燈右轉？", make_deps(FakeLLM(ANSWER)))
    started = [e.data.step for e in events if e.type == "step.started"]
    completed = [e.data.step for e in events if e.type == "step.completed"]
    assert started == completed == ["rewrite", "retrieve", "gate", "generate", "validate"]


def test_every_event_is_valid_against_the_schema_and_shares_the_run_id() -> None:
    events = collect("紅燈右轉？", make_deps(FakeLLM(ANSWER)))
    assert len({e.run_id for e in events}) == 1 and events[0].run_id
    for e in events:
        parsed = EVENT_ADAPTER.validate_python(e.model_dump())  # discriminated union 能還原
        assert parsed.type == e.type
        assert isinstance(e.ts, int) and e.ts > 0


def test_deltas_reassemble_the_full_answer_and_citations_are_reported() -> None:
    events = collect("紅燈右轉？", make_deps(FakeLLM(ANSWER, chunk_size=2)))
    text = "".join(e.data.text for e in events if e.type == "answer.delta")
    assert text == ANSWER
    citations = [e.data for e in events if e.type == "answer.citation"]
    assert [(c.marker, c.chunk_id) for c in citations] == [("[[K:53]]", "K:53")]
    for e in events:
        if e.type == "answer.delta":
            assert e.data.text.count("[[") == e.data.text.count("]]")  # 沒有半個標記


def test_retrieval_results_carry_everything_the_cards_need() -> None:
    events = collect("紅燈右轉？", make_deps(FakeLLM(ANSWER)))
    items = next(e for e in events if e.type == "retrieval.results").data.items
    assert [i.rank for i in items] == [1, 2]
    first = items[0]
    assert (first.chunk_id, first.law_name, first.law_short_name) == (
        "K:53", "道路交通管理處罰條例", "道交處罰條例",
    )  # fmt: skip
    assert first.score == 0.72 and first.source_url and first.amended_date == "20260817"
    assert first.snippet.startswith("處新臺幣")


def test_step_summaries_are_short_display_strings() -> None:
    events = collect("紅燈右轉？", make_deps(FakeLLM(ANSWER)))
    summary = {e.data.step: e.data.summary for e in events if e.type == "step.completed"}
    assert summary["rewrite"] == "未啟用"
    assert summary["retrieve"] == "top 2"
    assert summary["gate"] == "最高 0.72 ≥ 門檻 0.40"
    assert summary["generate"] == "1 個引用"
    assert summary["validate"] == "1 / 1 通過"
    assert all(e.data.duration_ms >= 0 for e in events if e.type == "step.completed")


def test_low_relevance_is_refused_by_the_gate_without_calling_the_model() -> None:
    llm = FakeLLM("不該被呼叫")
    events = collect("紅燈右轉？", make_deps(llm, score=0.30))
    assert llm.calls == []
    assert types(events)[-2:] == ["answer.refused", "run.completed"]
    refused = events[-2].data
    assert (refused.reason, refused.top_score, refused.threshold) == ("low_relevance", 0.30, 0.40)
    gate_done = [e for e in events if e.type == "step.completed" and e.data.step == "gate"][0]
    assert gate_done.data.summary == "最高 0.30 < 門檻 0.40"
    assert "answer.delta" not in types(events) and "validate.result" not in types(events)


def test_model_refusal_streams_no_text_and_reports_out_of_scope() -> None:
    events = collect("紅燈右轉？", make_deps(FakeLLM("[[REFUSE]]", chunk_size=2)))
    assert "answer.delta" not in types(events)
    refused = next(e for e in events if e.type == "answer.refused").data
    assert (refused.reason, refused.top_score, refused.threshold) == ("out_of_scope", 0.72, 0.40)
    assert types(events)[-1] == "run.completed" and "validate.result" not in types(events)


def test_safety_refusal_from_the_provider_is_reported_like_a_model_refusal() -> None:
    events = collect("紅燈右轉？", make_deps(FakeLLM("", refused=True)))
    assert next(e for e in events if e.type == "answer.refused").data.reason == "out_of_scope"


def test_invented_citation_is_reported_as_invalid() -> None:
    events = collect("紅燈右轉？", make_deps(FakeLLM("罰六百元[[K:53]]，依[[K:999]]。")))
    result = next(e for e in events if e.type == "validate.result").data
    assert result.valid == ["K:53"] and result.invalid == ["K:999"]
    summary = [e for e in events if e.type == "step.completed" and e.data.step == "validate"][0]
    assert summary.data.summary == "1 / 2 通過"


def test_error_during_the_stream_becomes_an_error_event_and_ends_normally() -> None:
    llm = FakeLLM(ANSWER, chunk_size=2, fail_after=3, error=LLMError("secret details"))
    events = collect("紅燈右轉？", make_deps(llm))
    assert events[-1].type == "error" and events[-1].data.code == "llm_error"
    assert "secret" not in events[-1].data.message  # 不把內部錯誤細節送給使用者
    assert "run.completed" not in types(events)
    assert "answer.delta" in types(events)  # 錯誤之前已送出的內容保留


class BrokenSearcher:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def search(self, question: str, k: int = 5) -> list[RetrievedChunk]:
        raise self._error


def test_retrieval_failure_becomes_an_error_event() -> None:
    deps = make_deps(FakeLLM(ANSWER), searcher=BrokenSearcher(EmbeddingError("api down")))
    events = collect("紅燈右轉？", deps)
    assert types(events)[-1] == "error" and events[-1].data.code == "embedding_error"
    assert types(events)[:3] == ["run.started", "step.started", "rewrite.result"]


def test_unexpected_exception_does_not_leak_details() -> None:
    deps = make_deps(FakeLLM(ANSWER), searcher=BrokenSearcher(RuntimeError("db password=hunter2")))
    events = collect("紅燈右轉？", deps)
    assert events[-1].data.code == "internal_error"
    assert "hunter2" not in events[-1].data.message


def test_closing_the_stream_early_closes_the_model_stream() -> None:
    """使用者斷線：呼叫端關閉產生器，對模型的串流也要跟著關閉（停止計費）。"""
    llm = FakeLLM(ANSWER, chunk_size=2)
    gen = run_ask("紅燈右轉？", make_deps(llm))
    for event in gen:
        if event.type == "answer.delta":
            break
    gen.close()
    assert llm.closed


def test_rewrite_enabled_runs_the_rewrite_and_reports_queries() -> None:
    def respond(system: str, user: str) -> str:
        return '{"queries": ["闖紅燈 右轉"]}' if "檢索助理" in system else ANSWER

    searcher = FakeSearcher(
        {
            "紅燈右轉？": [hit("K:53", "處新臺幣六百元以上一千八百元以下罰鍰。", 0.72)],
            "闖紅燈 右轉": [hit("K:58", "另一條", 0.60)],
        }
    )
    events = collect("紅燈右轉？", make_deps(FakeLLM(respond), rewrite=True, searcher=searcher))
    queries = next(e for e in events if e.type == "rewrite.result").data.queries
    assert queries == ["紅燈右轉？", "闖紅燈 右轉"]
    summary = {e.data.step: e.data.summary for e in events if e.type == "step.completed"}
    assert summary["rewrite"] == "2 個查詢"


@pytest.mark.parametrize(
    "llm_text",
    [ANSWER, "[[REFUSE]]", "罰六百元[[K:53]]，依[[K:999]]。", "沒有任何引用的回答"],
)
def test_streaming_and_non_streaming_pipelines_agree(llm_text: str) -> None:
    """兩條流程的重複部分不能悄悄分岔：同樣的模型輸出，結論必須一致。"""
    deps = make_deps(FakeLLM(llm_text, chunk_size=3))
    events = collect("紅燈右轉？", deps)
    reference = answer_question(
        "紅燈右轉？",
        searcher=deps.searcher,
        articles=deps.articles,
        llm=FakeLLM(llm_text),
        threshold=0.40,
    )
    refused = any(e.type == "answer.refused" for e in events)
    assert refused == reference.refused
    if not refused:
        text = "".join(e.data.text for e in events if e.type == "answer.delta")
        assert text == reference.answer
        result = next(e for e in events if e.type == "validate.result").data
        assert result.valid == reference.citations_valid
        assert result.invalid == reference.citations_invalid
