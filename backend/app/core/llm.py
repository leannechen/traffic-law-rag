"""LLMClient 介面與 Claude 實作。

pipeline 只依賴 LLMClient，測試與評估可換成假實作或有快取的包裝。
"""

import hashlib
import json
from collections.abc import Generator
from pathlib import Path
from typing import Any, Literal, Protocol

import anthropic
from pydantic import BaseModel

Effort = Literal["low", "medium", "high"]

# 伺服器端 fallback：模型被安全分類器擋下時，API 在同一次呼叫內換模型重試。
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMResponse(BaseModel):
    text: str
    model: str
    refused: bool = False  # stop_reason == "refusal"（含 fallback 也被拒）
    stop_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class LLMError(Exception):
    pass


class LLMClient(Protocol):
    model: str

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: Effort,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse: ...

    def stream(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: Effort,
    ) -> Generator[str | LLMResponse, None, None]:
        """逐段產生文字（str），最後一個元素是完整的 LLMResponse（含用量與是否被拒）。"""
        ...


class AnthropicLLMClient:
    """Claude API（Python SDK）。

    - 不設 temperature／top_p（Sonnet 5.5 不接受非預設值）。
    - 不傳 thinking：預設為 adaptive；深度以 effort 控制。
    - 以 content block 的 type 取文字，不依位置（thinking block 可能排在前面且內容為空）。
    """

    def __init__(
        self, api_key: str, model: str, use_fallbacks: bool = True, timeout: float = 60.0
    ) -> None:
        if not api_key:
            raise LLMError("缺少 ANTHROPIC_API_KEY，請設定在 .env")
        self.model = model
        self._use_fallbacks = use_fallbacks
        # 逾時：連線與「兩段資料之間」最久等多久；超過就丟 APITimeoutError → LLMError → error 事件
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

    def _request_params(
        self,
        system: str,
        user: str,
        max_tokens: int,
        effort: Effort,
        json_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        output_config: dict[str, Any] = {"effort": effort}
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        return {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": output_config,
        }

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: Effort,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        params = self._request_params(system, user, max_tokens, effort, json_schema)
        try:
            if self._use_fallbacks:
                response: Any = self._client.beta.messages.create(
                    **params, betas=[FALLBACK_BETA], fallbacks="default"
                )
            else:
                response = self._client.messages.create(**params)
        except anthropic.APITimeoutError as e:
            raise LLMError("呼叫 Claude API 逾時") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("無法連線 Claude API") from e
        except anthropic.APIStatusError as e:  # 含 RateLimitError、BadRequestError 等
            raise LLMError(f"Claude API 回應 {e.status_code}：{e.message}") from e
        text = "".join(b.text for b in response.content if b.type == "text")
        return LLMResponse(
            text=text,
            model=response.model,
            refused=response.stop_reason == "refusal",
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def stream(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: Effort,
    ) -> Generator[str | LLMResponse, None, None]:
        params = self._request_params(system, user, max_tokens, effort, None)
        try:
            if self._use_fallbacks:
                manager: Any = self._client.beta.messages.stream(
                    **params, betas=[FALLBACK_BETA], fallbacks="default"
                )
            else:
                manager = self._client.messages.stream(**params)
            # 離開 with（含呼叫端關閉這個產生器）時會關閉 HTTP 串流，停止產生與計費
            with manager as stream:
                yield from stream.text_stream
                final: Any = stream.get_final_message()
        except anthropic.APITimeoutError as e:
            raise LLMError("呼叫 Claude API 逾時") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("無法連線 Claude API") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Claude API 回應 {e.status_code}：{e.message}") from e
        yield LLMResponse(
            text="".join(b.text for b in final.content if b.type == "text"),
            model=final.model,
            refused=final.stop_reason == "refusal",
            stop_reason=final.stop_reason,
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
        )


class CachedLLMClient:
    """把成功的回應存在本機 JSON（鍵 = 模型＋參數＋prompt 內容的雜湊）。

    用於評估：重跑不重複呼叫、結果可重現、不花錢。被拒絕的回應不快取。
    """

    def __init__(self, inner: LLMClient, path: Path, refresh: bool = False) -> None:
        self._inner = inner
        self._path = path
        self._refresh = refresh
        self.model = inner.model
        self.cache_hits = 0
        self.calls = 0
        self._cache: dict[str, Any] = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        )

    def _key(self, system: str, user: str, max_tokens: int, effort: str, schema: Any) -> str:
        payload = json.dumps(
            [self.model, system, user, max_tokens, effort, schema],
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: Effort,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        key = self._key(system, user, max_tokens, effort, json_schema)
        if key in self._cache and not self._refresh:
            self.cache_hits += 1
            return LLMResponse.model_validate(self._cache[key])
        self.calls += 1
        response = self._inner.complete(
            system=system, user=user, max_tokens=max_tokens, effort=effort, json_schema=json_schema
        )
        if not response.refused:
            self._cache[key] = response.model_dump()
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")
        return response

    def stream(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: Effort,
    ) -> Generator[str | LLMResponse, None, None]:
        """串流不快取（評估不走串流路徑），直接轉給內層。"""
        return self._inner.stream(system=system, user=user, max_tokens=max_tokens, effort=effort)
