"""E2E 測試用的後端：真的 FastAPI、SSE、速率限制與錯誤處理，只有「模型、檢索、條文」換成假的。

    uv run python -m tests.e2e_server --port 8041

這樣 CI 不需要任何金鑰或索引，瀏覽器卻是走完整條 HTTP／SSE 路徑。
所有條文與答案都是刻意寫的假資料（不是真實法條，也不取自設計稿）。
"""

import argparse
import json
import os
import tempfile
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

# 必須在 import app 之前設定：get_settings() 只讀一次
_DATA_DIR = Path(tempfile.mkdtemp(prefix="traffic-law-e2e-"))
os.environ["DATA_DIR"] = str(_DATA_DIR)
os.environ["RATE_LIMIT_REQUESTS"] = "1000"

import uvicorn  # noqa: E402

from app.api.deps import get_ask_deps, get_chunk_store  # noqa: E402
from app.api.eval import get_eval_path  # noqa: E402
from app.core.llm import Effort, LLMResponse  # noqa: E402
from app.ingestion.build_index import META_FILE  # noqa: E402
from app.main import app  # noqa: E402
from app.pipeline.ask_stream import AskDeps  # noqa: E402
from app.schemas.chunk import ChunkDetail  # noqa: E402
from app.schemas.meta import IndexMeta, LawMeta  # noqa: E402
from app.schemas.retrieval import RetrievedChunk  # noqa: E402
from tests.fakes import FakeArticles, FakeLLM, FakeSearcher, chunk  # noqa: E402

PCODE = "T0000001"
LAW_NAME, LAW_SHORT = "測試用處罰條例", "測試條例"
TEXTS = {
    f"{PCODE}:53": "第五十三條　測試條文甲。\n前項測試條文乙。",
    f"{PCODE}:53-1": "第五十三條之一　測試條文丙。",
    f"{PCODE}:35": "第三十五條　第一項的測試內容。\n第二項的測試內容，這是被切成兩塊的長條文。",
    f"{PCODE}:58": "第五十八條　測試條文丁。",
}

Q_RED = "紅燈右轉會被罰多少錢？"
Q_DRUNK = "酒駕被抓到會有什麼處罰？"
Q_BUS = "公車專用道可以走嗎？"
Q_WEATHER = "今天天氣怎麼樣？"


def hit(chunk_id: str, score: float, rank: int) -> RetrievedChunk:
    article = chunk_id.split("-p")[0]
    return chunk(chunk_id, TEXTS[article], score, law=LAW_SHORT, rank=rank).model_copy(
        update={
            "law_name": LAW_NAME,
            "source_url": f"https://example.test/law/{article}",
            "amended_date": "20000101",
        }
    )


RESULTS = {
    Q_RED: [
        hit(f"{PCODE}:53", 0.80, 1),
        hit(f"{PCODE}:53-1", 0.75, 2),
        hit(f"{PCODE}:58", 0.60, 3),
    ],
    Q_DRUNK: [hit(f"{PCODE}:35-p1", 0.85, 1), hit(f"{PCODE}:35-p2", 0.80, 2)],
    Q_BUS: [hit(f"{PCODE}:58", 0.55, 1)],
    Q_WEATHER: [hit(f"{PCODE}:58", 0.20, 1)],
}

ANSWERS = {
    Q_RED: "測試回答第一段，說明甲[[T0000001:53]]。第二段說明丙[[T0000001:53-1]]。",
    Q_DRUNK: "測試回答：這個行為有處罰規定[[T0000001:35]]。",
    Q_BUS: "[[REFUSE]]",
}


class SlowLLM(FakeLLM):
    """每段之間停一下，讓 E2E 有機會在串流中途按「停止」。"""

    def stream(
        self, *, system: str, user: str, max_tokens: int, effort: Effort
    ) -> Generator[str | LLMResponse, None, None]:
        inner = super().stream(system=system, user=user, max_tokens=max_tokens, effort=effort)
        try:
            for piece in inner:
                time.sleep(0.12)
                yield piece
        finally:
            inner.close()


def respond(system: str, user: str) -> str:
    for question, answer in ANSWERS.items():
        if question in user:
            return answer
    return "[[REFUSE]]"


class FakeChunkStore:
    def get(self, chunk_id: str) -> ChunkDetail | None:
        article = chunk_id.split("-p")[0]
        if article not in TEXTS:
            return None
        no = article.split(":")[1]
        return ChunkDetail(
            chunk_id=chunk_id,
            article_id=article,
            pcode=PCODE,
            law_name=LAW_NAME,
            law_short_name=LAW_SHORT,
            law_level="法律",
            article_no=no,
            text=TEXTS[article],
            source_url=f"https://example.test/law/{article}",
            amended_date="20000101",
            data_version="2000-01-01",
            article_text=TEXTS[article],
        )


def eval_fixture() -> dict[str, Any]:
    def row(i: int, **extra: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "id": f"q{i:02d}",
            "question": f"測試題目 {i}",
            "category": "fine_amount",
            "should_refuse": False,
            "expected": [f"{PCODE}:53"],
            "retrieved_top": [{"article_id": f"{PCODE}:53", "score": 0.8}],
            "refused": False,
            "citations_invalid": [],
            "numbers_total": 1,
            "numbers_unmatched": [],
            "recall_at_5": 1.0,
            "reciprocal_rank": 1.0,
            "citation_hit": True,
        }
        return {**base, **extra}

    return {
        "name": "e2e",
        "evaluated_at": "2000-01-02T00:00:00+00:00",
        "config": {"data_version": "2000-01-01"},
        "counts": {"verified": 3, "answerable": 2, "out_of_scope": 1},
        "metrics": {
            "recall_at_5": 1.0,
            "mrr": 0.75,
            "citation_accuracy": 1.0,
            "number_accuracy": 1.0,
            "refusal_accuracy": 1.0,
        },
        "questions": [
            row(1),
            row(2, category="accident", recall_at_5=0.5, reciprocal_rank=0.5),
            row(3, category="out_of_scope", should_refuse=True, expected=[], refused=True),
        ],
    }


def build_app() -> Any:
    index_dir = _DATA_DIR / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    meta = IndexMeta(
        data_version="2000-01-01",
        built_at="2000-01-01T00:00:00+00:00",
        embedding_model="fake",
        chunk_count=4,
        laws=[
            LawMeta(
                pcode=PCODE,
                law_name=LAW_NAME,
                law_short_name=LAW_SHORT,
                law_level="法律",
                article_count=4,
                chunk_count=4,
                amended_date="20000101",
            )
        ],
    )
    (index_dir / META_FILE).write_text(meta.model_dump_json(), encoding="utf-8")
    eval_path = _DATA_DIR / "latest.json"
    eval_path.write_text(json.dumps(eval_fixture(), ensure_ascii=False), encoding="utf-8")

    deps = AskDeps(
        searcher=FakeSearcher(RESULTS),
        articles=FakeArticles(TEXTS),
        llm=SlowLLM(respond, chunk_size=6),
        gate_threshold=0.40,
        rewrite_enabled=False,
    )
    app.dependency_overrides[get_ask_deps] = lambda: deps
    app.dependency_overrides[get_chunk_store] = lambda: FakeChunkStore()
    app.dependency_overrides[get_eval_path] = lambda: eval_path
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8041)
    args = parser.parse_args()
    uvicorn.run(build_app(), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
