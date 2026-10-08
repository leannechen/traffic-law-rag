"""VoyageEmbedder 的 HTTP 行為：批次、排序、重試、錯誤轉換。不連線，urlopen 用假的取代。"""

import io
import json
import urllib.error
from typing import Any

import pytest

from app.core.embedder import EmbeddingError, VoyageEmbedder


class FakeResponse(io.BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def ok(vectors: list[list[float]], order: list[int] | None = None) -> FakeResponse:
    indexes = order if order is not None else list(range(len(vectors)))
    data = [{"index": i, "embedding": v} for i, v in zip(indexes, vectors, strict=True)]
    return FakeResponse(json.dumps({"data": data}).encode())


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(b"body"))  # type: ignore[arg-type]


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    recorded: list[dict[str, Any]] = []
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _next(recorded, req))
    return recorded


queue: list[Any] = []


def _next(recorded: list[dict[str, Any]], req: Any) -> FakeResponse:
    recorded.append(json.loads(req.data))
    item = queue.pop(0)
    if isinstance(item, Exception):
        raise item
    return item  # type: ignore[no-any-return]


@pytest.fixture(autouse=True)
def clear_queue() -> None:
    queue.clear()


def test_missing_key_is_a_clear_error() -> None:
    with pytest.raises(EmbeddingError, match="VOYAGE_API_KEY"):
        VoyageEmbedder("")


def test_texts_are_sent_in_batches_with_the_input_type(calls: list[dict[str, Any]]) -> None:
    queue.extend([ok([[1.0], [2.0]]), ok([[3.0]])])
    vectors = VoyageEmbedder("key", batch_size=2).embed(["a", "b", "c"], "query")
    assert vectors == [[1.0], [2.0], [3.0]]
    assert [c["input"] for c in calls] == [["a", "b"], ["c"]]
    assert all(c["input_type"] == "query" and c["model"] == "voyage-4" for c in calls)


def test_vectors_are_returned_in_input_order_even_if_the_api_shuffles_them(
    calls: list[dict[str, Any]],
) -> None:
    queue.append(ok([[2.0], [1.0]], order=[1, 0]))
    assert VoyageEmbedder("key").embed(["a", "b"], "document") == [[1.0], [2.0]]


def test_transient_errors_are_retried_then_succeed(calls: list[dict[str, Any]]) -> None:
    queue.extend([http_error(429), http_error(503), ok([[1.0]])])
    assert VoyageEmbedder("key").embed(["a"], "document") == [[1.0]]
    assert len(calls) == 3


def test_gives_up_after_the_retries_with_the_status_code(calls: list[dict[str, Any]]) -> None:
    queue.extend([http_error(429)] * 4)
    with pytest.raises(EmbeddingError, match="429"):
        VoyageEmbedder("key").embed(["a"], "document")
    assert len(calls) == 4


def test_client_errors_are_not_retried(calls: list[dict[str, Any]]) -> None:
    queue.append(http_error(401))
    with pytest.raises(EmbeddingError, match="401"):
        VoyageEmbedder("key").embed(["a"], "document")
    assert len(calls) == 1


def test_network_failures_are_retried_and_reported(calls: list[dict[str, Any]]) -> None:
    queue.extend([urllib.error.URLError("down")] * 4)
    with pytest.raises(EmbeddingError, match="無法連線"):
        VoyageEmbedder("key").embed(["a"], "document")
    assert len(calls) == 4
