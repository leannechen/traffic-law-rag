import json
import time
from collections.abc import Generator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import ask as ask_module
from app.api.deps import get_ask_deps, get_chunk_store, get_rate_limiter
from app.core.embedder import EmbeddingError
from app.core.llm import LLMError
from app.core.rate_limit import RateLimiter
from app.main import app
from app.pipeline.ask_stream import AskDeps
from app.schemas.events import RunStarted, RunStartedData
from tests.fakes import FakeArticles, FakeLLM, FakeSearcher, chunk

ANSWER = "紅燈右轉罰六百元以上一千八百元以下[[K:53]]。"


def make_deps(llm: FakeLLM | None = None, score: float = 0.72) -> AskDeps:
    hits = [chunk("K:53", "處新臺幣六百元以上一千八百元以下罰鍰。", score)]
    return AskDeps(
        searcher=FakeSearcher({"紅燈右轉？": hits}),
        articles=FakeArticles(),
        llm=llm or FakeLLM(ANSWER, chunk_size=3),
        gate_threshold=0.40,
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_ask_deps] = lambda: make_deps()
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(100, 60)
    yield TestClient(app)
    app.dependency_overrides.clear()


def parse_sse(lines: Iterator[str]) -> list[dict[str, Any]]:
    events, current = [], {}
    for line in lines:
        if line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("data: "):
            current["data"] = json.loads(line[6:])
        elif line == "" and current:
            events.append(current)
            current = {}
    return events


def ask(client: TestClient, question: str = "紅燈右轉？") -> list[dict[str, Any]]:
    with client.stream("POST", "/api/ask", json={"question": question}) as res:
        assert res.status_code == 200
        return parse_sse(res.iter_lines())


def test_streams_events_in_the_documented_order(client: TestClient) -> None:
    events = ask(client)
    types = [e["data"]["type"] for e in events]
    assert types[0] == "run.started" and types[-1] == "run.completed"
    assert types.count("step.started") == types.count("step.completed") == 5
    assert "answer.citation" in types and "validate.result" in types


def test_sse_framing_and_envelope(client: TestClient) -> None:
    events = ask(client)
    for e in events:
        assert e["event"] == e["data"]["type"]  # event: 行與外框的 type 一致
        assert set(e["data"]) == {"type", "run_id", "ts", "data"}
    assert events[0]["data"]["data"] == {"question": "紅燈右轉？"}


def test_response_headers_disable_buffering_and_caching(client: TestClient) -> None:
    with client.stream("POST", "/api/ask", json={"question": "紅燈右轉？"}) as res:
        assert res.headers["content-type"].startswith("text/event-stream")
        assert "no-cache" in res.headers["cache-control"]
        assert res.headers["x-accel-buffering"] == "no"
        list(res.iter_lines())


def test_chinese_is_sent_as_text_not_unicode_escapes(client: TestClient) -> None:
    with client.stream("POST", "/api/ask", json={"question": "紅燈右轉？"}) as res:
        raw = "\n".join(res.iter_lines())
    assert "紅燈右轉" in raw and "\\u7d05" not in raw


def test_refusal_stream(client: TestClient) -> None:
    app.dependency_overrides[get_ask_deps] = lambda: make_deps(score=0.2)
    events = ask(client)
    refused = [e for e in events if e["event"] == "answer.refused"]
    assert refused[0]["data"]["data"] == {
        "reason": "low_relevance", "top_score": 0.2, "threshold": 0.4,
    }  # fmt: skip
    assert events[-1]["event"] == "run.completed"


def test_error_is_an_event_not_an_http_failure(client: TestClient) -> None:
    llm = FakeLLM(ANSWER, chunk_size=2, fail_after=2, error=RuntimeError("boom"))
    app.dependency_overrides[get_ask_deps] = lambda: make_deps(llm)
    events = ask(client)  # 狀態碼仍是 200，串流正常結束
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["data"]["code"] == "internal_error"


@pytest.mark.parametrize("body", [{"question": ""}, {"question": "   "}, {}, {"question": 5}])
def test_invalid_questions_are_rejected_with_422(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/api/ask", json=body).status_code == 422


def test_question_length_limit_is_200_characters(client: TestClient) -> None:
    ok = client.post("/api/ask", json={"question": "字" * 200})
    assert ok.status_code == 200
    too_long = client.post("/api/ask", json={"question": "字" * 201})
    assert too_long.status_code == 422


def test_question_is_stripped(client: TestClient) -> None:
    events = ask(client, "  紅燈右轉？  ")
    assert events[0]["data"]["data"]["question"] == "紅燈右轉？"


def test_rate_limit_returns_429_with_retry_after(client: TestClient) -> None:
    limiter = RateLimiter(2, 60)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    assert client.post("/api/ask", json={"question": "紅燈右轉？"}).status_code == 200
    assert client.post("/api/ask", json={"question": "紅燈右轉？"}).status_code == 200
    blocked = client.post("/api/ask", json={"question": "紅燈右轉？"})
    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["retry-after"]) <= 60
    assert blocked.json()["detail"]


def test_invalid_requests_do_not_consume_the_rate_limit(client: TestClient) -> None:
    limiter = RateLimiter(1, 60)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    for _ in range(3):
        assert client.post("/api/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/ask", json={"question": "紅燈右轉？"}).status_code == 200


def test_cors_exposes_retry_after_header(client: TestClient) -> None:
    res = client.options(
        "/api/ask",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert res.status_code == 200
    assert "POST" in res.headers["access-control-allow-methods"]


@pytest.mark.parametrize(
    "error", [EmbeddingError("no key"), LLMError("no key"), ValueError("no index")]
)
def test_missing_keys_or_index_give_503_not_500(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    import app.api.deps as deps_module

    def broken() -> AskDeps:
        raise error

    monkeypatch.setattr(deps_module, "_build_ask_deps", broken)
    res = TestClient(app).post("/api/ask", json={"question": "紅燈右轉？"})
    assert res.status_code == 503 and res.json()["detail"]


def test_heartbeat_comment_is_sent_while_waiting(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def slow(question: str, deps: AskDeps) -> Generator[Any, None, None]:
        yield RunStarted(run_id="r", data=RunStartedData(question=question))
        time.sleep(0.35)
        yield RunStarted(run_id="r", data=RunStartedData(question="後面的事件"))

    monkeypatch.setattr(ask_module, "run_ask", slow)
    monkeypatch.setattr(ask_module, "HEARTBEAT_SECONDS", 0.1)
    with client.stream("POST", "/api/ask", json={"question": "x"}) as res:
        lines = list(res.iter_lines())
    assert any(line == ": keep-alive" for line in lines)
    assert sum(1 for line in lines if line.startswith("event: run.started")) == 2


def test_event_generator_is_closed_when_the_response_ends(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[bool] = []

    def gen(question: str, deps: AskDeps) -> Generator[Any, None, None]:
        try:
            yield RunStarted(run_id="r", data=RunStartedData(question=question))
            yield RunStarted(run_id="r", data=RunStartedData(question=question))
        finally:
            closed.append(True)

    monkeypatch.setattr(ask_module, "run_ask", gen)
    with client.stream("POST", "/api/ask", json={"question": "x"}) as res:
        list(res.iter_lines())
    assert closed == [True]


def test_chunks_endpoint_dependency_is_overridable_and_404s_unknown() -> None:
    class EmptyStore:
        def get(self, chunk_id: str) -> None:
            return None

    app.dependency_overrides[get_chunk_store] = lambda: EmptyStore()
    try:
        assert TestClient(app).get("/api/chunks/K0040012:999").status_code == 404
    finally:
        app.dependency_overrides.clear()
