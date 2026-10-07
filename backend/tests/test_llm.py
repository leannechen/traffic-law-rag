from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2 as httpx
import pytest

from app.core.llm import FALLBACK_BETA, AnthropicLLMClient, CachedLLMClient, LLMError, LLMResponse
from tests.fakes import FakeLLM


class FakeMessages:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.kwargs: dict[str, Any] = {}
        self._response = response
        self._error = error

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self._error:
            raise self._error
        return self._response


def sdk_response(blocks: list[Any], stop_reason: str = "end_turn") -> Any:
    return SimpleNamespace(
        content=blocks,
        model="claude-sonnet-5-5",
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


def client_with(messages: FakeMessages, *, fallbacks: bool = True) -> AnthropicLLMClient:
    client = AnthropicLLMClient("test-key", "claude-sonnet-5-5", use_fallbacks=fallbacks)
    client._client = SimpleNamespace(beta=SimpleNamespace(messages=messages), messages=messages)  # type: ignore[assignment]
    return client


THINKING = SimpleNamespace(type="thinking", thinking="")
TEXT = SimpleNamespace(type="text", text="答案[[K:1]]")


def test_request_has_no_sampling_params_and_no_forbidden_thinking() -> None:
    messages = FakeMessages(sdk_response([TEXT]))
    client_with(messages).complete(system="S", user="U", max_tokens=100, effort="low")
    kw = messages.kwargs
    for forbidden in ("temperature", "top_p", "top_k", "thinking", "tool_choice"):
        assert forbidden not in kw
    assert kw["model"] == "claude-sonnet-5-5"
    assert kw["output_config"] == {"effort": "low"}
    assert kw["system"] == "S" and kw["messages"] == [{"role": "user", "content": "U"}]


def test_fallbacks_enabled_by_default_use_the_default_form() -> None:
    messages = FakeMessages(sdk_response([TEXT]))
    client_with(messages).complete(system="S", user="U", max_tokens=10, effort="medium")
    assert messages.kwargs["betas"] == [FALLBACK_BETA]
    assert messages.kwargs["fallbacks"] == "default"


def test_fallbacks_can_be_turned_off() -> None:
    messages = FakeMessages(sdk_response([TEXT]))
    client_with(messages, fallbacks=False).complete(
        system="S", user="U", max_tokens=10, effort="medium"
    )
    assert "betas" not in messages.kwargs and "fallbacks" not in messages.kwargs


def test_json_schema_goes_into_output_config_format() -> None:
    messages = FakeMessages(sdk_response([TEXT]))
    schema = {"type": "object"}
    client_with(messages).complete(
        system="S", user="U", max_tokens=10, effort="low", json_schema=schema
    )
    assert messages.kwargs["output_config"]["format"] == {"type": "json_schema", "schema": schema}


def test_text_is_read_by_block_type_not_position() -> None:
    messages = FakeMessages(sdk_response([THINKING, TEXT]))
    out = client_with(messages).complete(system="S", user="U", max_tokens=10, effort="low")
    assert out.text == "答案[[K:1]]" and not out.refused
    assert (out.input_tokens, out.output_tokens) == (100, 20)


def test_refusal_stop_reason_is_surfaced() -> None:
    messages = FakeMessages(sdk_response([], stop_reason="refusal"))
    out = client_with(messages).complete(system="S", user="U", max_tokens=10, effort="low")
    assert out.refused and out.text == ""


def test_missing_api_key_fails_early() -> None:
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        AnthropicLLMClient("", "claude-sonnet-5-5")


def _status_error(status: int) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request, json={"error": {"message": "boom"}})
    return anthropic.RateLimitError("rate limited", response=response, body=None)


def test_api_errors_become_llm_error() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    for error in (_status_error(429), anthropic.APITimeoutError(request=request)):
        messages = FakeMessages(error=error)
        with pytest.raises(LLMError):
            client_with(messages).complete(system="S", user="U", max_tokens=10, effort="low")


def test_cached_llm_calls_inner_once_for_identical_requests(tmp_path: Path) -> None:
    inner = FakeLLM("回答")
    cached = CachedLLMClient(inner, tmp_path / "c" / "llm.json")
    args: dict[str, Any] = {"system": "S", "user": "U", "max_tokens": 10, "effort": "low"}
    first = cached.complete(**args)
    second = cached.complete(**args)
    assert first == second and len(inner.calls) == 1 and cached.cache_hits == 1
    cached.complete(**{**args, "user": "U2"})
    assert len(inner.calls) == 2  # 內容不同要重新呼叫
    reloaded = CachedLLMClient(FakeLLM("不該被呼叫"), tmp_path / "c" / "llm.json")
    assert reloaded.complete(**args).text == "回答"  # 重新載入後仍有快取


def test_cached_llm_does_not_cache_refusals(tmp_path: Path) -> None:
    inner = FakeLLM("x", refused=True)
    cached = CachedLLMClient(inner, tmp_path / "llm.json")
    args: dict[str, Any] = {"system": "S", "user": "U", "max_tokens": 10, "effort": "low"}
    cached.complete(**args)
    cached.complete(**args)
    assert len(inner.calls) == 2


def test_cached_llm_refresh_ignores_existing_cache(tmp_path: Path) -> None:
    path = tmp_path / "llm.json"
    args: dict[str, Any] = {"system": "S", "user": "U", "max_tokens": 10, "effort": "low"}
    CachedLLMClient(FakeLLM("舊"), path).complete(**args)
    inner = FakeLLM("新")
    assert CachedLLMClient(inner, path, refresh=True).complete(**args).text == "新"


def test_request_timeout_is_bounded() -> None:
    client = AnthropicLLMClient("test-key", "claude-sonnet-5-5", timeout=7.0)
    assert client._client.timeout == 7.0  # 預設是 10 分鐘，使用者等不了那麼久
    assert AnthropicLLMClient("test-key", "claude-sonnet-5-5")._client.timeout == 60.0


class FakeStreamManager:
    def __init__(
        self,
        deltas: list[str],
        final: Any,
        *,
        error_after: int | None = None,
        error: Exception | None = None,
    ) -> None:
        self._deltas, self._final = deltas, final
        self._error_after, self._error = error_after, error
        self.exited = False
        self.text_stream = self._iterate()

    def _iterate(self) -> Iterator[str]:
        for i, d in enumerate(self._deltas):
            if self._error_after is not None and i >= self._error_after and self._error:
                raise self._error
            yield d

    def __enter__(self) -> "FakeStreamManager":
        return self

    def __exit__(self, *exc: object) -> None:
        self.exited = True

    def get_final_message(self) -> Any:
        return self._final


class FakeStreamingMessages:
    def __init__(self, manager: FakeStreamManager) -> None:
        self.kwargs: dict[str, Any] = {}
        self._manager = manager

    def stream(self, **kwargs: Any) -> FakeStreamManager:
        self.kwargs = kwargs
        return self._manager


def streaming_client(
    messages: FakeStreamingMessages, *, fallbacks: bool = True
) -> AnthropicLLMClient:
    client = AnthropicLLMClient("test-key", "claude-sonnet-5-5", use_fallbacks=fallbacks)
    client._client = SimpleNamespace(beta=SimpleNamespace(messages=messages), messages=messages)  # type: ignore[assignment]
    return client


def test_stream_yields_text_pieces_then_the_final_response() -> None:
    manager = FakeStreamManager(["紅燈", "右轉"], sdk_response([THINKING, TEXT]))
    messages = FakeStreamingMessages(manager)
    items = list(
        streaming_client(messages).stream(system="S", user="U", max_tokens=10, effort="medium")
    )
    assert items[:2] == ["紅燈", "右轉"]
    final = items[2]
    assert isinstance(final, LLMResponse) and final.text == "答案[[K:1]]"
    assert (final.input_tokens, final.output_tokens) == (100, 20)
    assert manager.exited  # 正常結束也會離開 with
    assert messages.kwargs["fallbacks"] == "default" and "temperature" not in messages.kwargs


def test_closing_the_stream_early_closes_the_http_stream() -> None:
    manager = FakeStreamManager(["a", "b", "c"], sdk_response([TEXT]))
    gen = streaming_client(FakeStreamingMessages(manager)).stream(
        system="S", user="U", max_tokens=10, effort="low"
    )
    assert next(gen) == "a"
    gen.close()  # 使用者斷線
    assert manager.exited


def test_stream_errors_become_llm_error() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    manager = FakeStreamManager(
        ["a", "b"],
        sdk_response([TEXT]),
        error_after=1,
        error=anthropic.APITimeoutError(request=request),
    )
    gen = streaming_client(FakeStreamingMessages(manager)).stream(
        system="S", user="U", max_tokens=10, effort="low"
    )
    assert next(gen) == "a"
    with pytest.raises(LLMError, match="逾時"):
        next(gen)
    assert manager.exited


def test_stream_refusal_is_reported_in_the_final_response() -> None:
    manager = FakeStreamManager([], sdk_response([], stop_reason="refusal"))
    items = list(
        streaming_client(FakeStreamingMessages(manager)).stream(
            system="S", user="U", max_tokens=10, effort="low"
        )
    )
    assert isinstance(items[-1], LLMResponse) and items[-1].refused
