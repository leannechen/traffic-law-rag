import json
import time
import urllib.error
import urllib.request
from typing import Literal, Protocol

InputType = Literal["document", "query"]


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]: ...


class EmbeddingError(Exception):
    pass


class VoyageEmbedder:
    """Voyage AI embeddings（REST）。批次上限 1,000 筆，這裡用較小的批次。"""

    URL = "https://api.voyageai.com/v1/embeddings"

    def __init__(self, api_key: str, model: str = "voyage-4", batch_size: int = 128) -> None:
        if not api_key:
            raise EmbeddingError("缺少 VOYAGE_API_KEY，請設定在 .env")
        self._api_key = api_key
        self.model = model
        self._batch_size = batch_size

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            vectors.extend(self._request(texts[i : i + self._batch_size], input_type))
        return vectors

    def _request(self, batch: list[str], input_type: InputType) -> list[list[float]]:
        body = json.dumps({"input": batch, "model": self.model, "input_type": input_type}).encode()
        req = urllib.request.Request(
            self.URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as res:
                    data = json.load(res)
                items = sorted(data["data"], key=lambda d: d["index"])
                return [item["embedding"] for item in items]
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise EmbeddingError(f"Voyage API 回應 {e.code}：{e.read()[:200]!r}") from e
            except urllib.error.URLError as e:
                if attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise EmbeddingError(f"無法連線 Voyage API：{e.reason}") from e
        raise EmbeddingError("unreachable")
