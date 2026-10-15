from collections.abc import Awaitable, Callable
from typing import Any

import anyio
from mcp import Client
from mcp.server import MCPServer
from mcp.types import CallToolResult

from app.mcp_server import NOTICE, Asker, build_server, make_asker
from app.pipeline.articles import ArticleText
from app.schemas.retrieval import RetrievedChunk
from tests.fakes import FakeArticles as FakeTextArticles
from tests.fakes import FakeLLM, chunk
from tests.fakes import FakeSearcher as FakeResults


class FakeSearcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(self, question: str, k: int = 5) -> list[RetrievedChunk]:
        self.calls.append((question, k))
        return [chunk("K1:53", "只有第一塊", 0.71, law="處罰條例")]


class FakeArticles:
    def get(self, article_id: str) -> ArticleText | None:
        if article_id != "K1:53":
            return None
        return ArticleText(
            article_id="K1:53", law_short_name="處罰條例", article_no="53", text="整條全文"
        )


META = {"K1:53": {"amended_date": "20240101", "source_url": "https://example/53"}}


def no_ask(question: str) -> Any:
    raise AssertionError("不該呼叫 ask")


def make(ask: Asker = no_ask) -> tuple[MCPServer, FakeSearcher]:
    searcher = FakeSearcher()
    return build_server(searcher, FakeArticles(), "2026-10-05", META, ask), searcher


ART53 = chunk("K1:53", "處新臺幣六百元以上一千八百元以下罰鍰。", 0.72, law="處罰條例")


def make_ask(
    llm: FakeLLM, score: float = 0.72, texts: dict[str, str] | None = None
) -> tuple[MCPServer, FakeLLM]:
    results = FakeResults({"紅燈右轉？": [ART53.model_copy(update={"vector_score": score})]})
    articles = FakeTextArticles(texts or {"K1:53": ART53.text})
    ask = make_asker(results, articles, lambda: llm, threshold=0.40)
    return build_server(FakeSearcher(), FakeArticles(), "2026-10-05", META, ask), llm


def run[T](fn: Callable[[], Awaitable[T]]) -> T:
    return anyio.run(fn)


def call(server: MCPServer, name: str, args: dict[str, Any]) -> CallToolResult:
    async def go() -> CallToolResult:
        async with Client(server) as client:
            return await client.call_tool(name, args)

    return run(go)


def test_search_returns_whole_article_with_score_and_notice() -> None:
    server, searcher = make()
    result = call(server, "search_traffic_law", {"query": "紅燈右轉", "k": 3})
    data = result.structured_content
    assert data is not None
    assert searcher.calls == [("紅燈右轉", 3)]
    assert data["data_version"] == "2026-10-05"
    assert data["notice"] == NOTICE
    (hit,) = data["results"]
    assert hit["article_id"] == "K1:53"
    assert hit["text"] == "整條全文"  # 整條，不是命中的那一塊
    assert hit["score"] == 0.71


def test_search_rejects_empty_overlong_and_out_of_range() -> None:
    server, searcher = make()
    bad_args: list[dict[str, Any]] = [
        {"query": "  "},
        {"query": "字" * 201},
        {"query": "紅燈", "k": 0},
        {"query": "紅燈", "k": 11},
    ]
    for args in bad_args:
        assert call(server, "search_traffic_law", args).is_error, args
    assert searcher.calls == []


def test_get_article_and_not_found() -> None:
    server, _ = make()
    ok = call(server, "get_article", {"article_id": "K1:53"})
    assert ok.structured_content is not None
    assert ok.structured_content["source_url"] == "https://example/53"
    assert ok.structured_content["amended_date"] == "20240101"
    assert call(server, "get_article", {"article_id": "K1:999"}).is_error


def test_tools_are_read_only_and_state_scope() -> None:
    server, _ = make()

    async def go() -> Any:
        async with Client(server) as client:
            return await client.list_tools()

    tools = run(go).tools
    assert {t.name for t in tools} == {"ask_traffic_law", "search_traffic_law", "get_article"}
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)
    assert all("裁罰基準" in (t.description or "") for t in tools)


def test_ask_returns_validated_answer_with_citations() -> None:
    server, _ = make_ask(FakeLLM("紅燈右轉罰六百元以上一千八百元以下[[K1:53]]。"))
    data = call(server, "ask_traffic_law", {"question": "紅燈右轉？"}).structured_content
    assert data is not None
    assert data["refused"] is False
    assert "[[K1:53]]" in data["answer"]
    assert data["citations"] == [
        {
            "article_id": "K1:53",
            "law": "處罰條例",
            "article_no": "53",
            "source_url": "https://example/53",
        }
    ]
    assert data["citations_invalid"] == [] and data["numbers_unmatched"] == []
    assert data["data_version"] == "2026-10-05"


def test_ask_surfaces_invalid_citations_and_wrong_numbers() -> None:
    server, _ = make_ask(FakeLLM("罰九千九百元[[K1:53]][[K9:9]]。"))
    data = call(server, "ask_traffic_law", {"question": "紅燈右轉？"}).structured_content
    assert data is not None
    assert data["citations_invalid"] == ["K9:9"]
    assert data["numbers_unmatched"]  # 九千九百元不在條文裡


def test_ask_gate_refusal_does_not_call_the_model() -> None:
    server, llm = make_ask(FakeLLM("不該被呼叫"), score=0.30)
    data = call(server, "ask_traffic_law", {"question": "紅燈右轉？"}).structured_content
    assert data is not None
    assert data["refused"] is True and data["refusal_layer"] == "gate"
    assert data["answer"] == "" and data["refusal_message"]
    assert llm.calls == []


def test_ask_model_refusal() -> None:
    server, _ = make_ask(FakeLLM("[[REFUSE]]"))
    data = call(server, "ask_traffic_law", {"question": "紅燈右轉？"}).structured_content
    assert data is not None
    assert data["refused"] is True and data["refusal_layer"] == "model"


def test_ask_truncated_answer_is_an_error_not_an_answer() -> None:
    server, _ = make_ask(FakeLLM("答案寫到一半[[K1:53]]", stop_reason="max_tokens"))
    assert call(server, "ask_traffic_law", {"question": "紅燈右轉？"}).is_error


def test_ask_rejects_empty_and_overlong_question() -> None:
    server, llm = make_ask(FakeLLM("不該被呼叫"))
    for q in ("  ", "字" * 201):
        assert call(server, "ask_traffic_law", {"question": q}).is_error
    assert llm.calls == []


def test_ask_without_api_key_does_not_break_search_tools() -> None:
    def no_key() -> FakeLLM:
        raise ValueError("缺少 ANTHROPIC_API_KEY")

    ask = make_asker(FakeResults({}), FakeTextArticles(), no_key, threshold=0.40)
    server, _ = make(ask)
    assert call(server, "ask_traffic_law", {"question": "紅燈右轉？"}).is_error
    assert not call(server, "search_traffic_law", {"query": "紅燈右轉"}).is_error
