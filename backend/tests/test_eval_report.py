import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.eval import get_eval_path
from app.main import app
from app.pipeline.eval_report import build_report


def row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "q01",
        "question": "紅燈右轉會被罰多少錢？",
        "category": "fine_amount",
        "should_refuse": False,
        "expected": ["K0040012:53"],
        "retrieved_top": [{"article_id": "K0040012:53", "score": 0.91}],
        "refused": False,
        "citations_invalid": [],
        "numbers_total": 2,
        "numbers_unmatched": [],
        "recall_at_5": 1.0,
        "reciprocal_rank": 1.0,
        "citation_hit": True,
        "fact_amounts_expected": 2,
        "fact_amounts_found": 2,
    }
    return {**base, **overrides}


def raw(*rows: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "test-run",
        "evaluated_at": "2000-01-01T00:00:00+00:00",
        "config": {"data_version": "2000-01-01"},
        "counts": {"verified": len(rows), "answerable": len(rows), "out_of_scope": 0},
        "metrics": {
            "recall_at_5": 1.0,
            "mrr": 0.8,
            "citation_accuracy": 0.9,
            "number_accuracy": None,
            "refusal_accuracy": 1.0,
        },
        "questions": list(rows),
    }


def only(**overrides: Any):  # type: ignore[no-untyped-def]
    return build_report(raw(row(**overrides))).questions[0]


def test_hit_miss_and_partial_retrieval_with_rank() -> None:
    assert (only().retrieval, only().first_hit_rank) == ("hit", 1)
    second = only(reciprocal_rank=0.5)
    assert (second.retrieval, second.first_hit_rank) == ("hit", 2)
    assert only(recall_at_5=0.5, reciprocal_rank=1.0).retrieval == "partial"
    miss = only(recall_at_5=0.0, reciprocal_rank=0.0)
    assert (miss.retrieval, miss.first_hit_rank) == ("miss", None)


def test_citation_states() -> None:
    assert only().citation == "ok"
    assert only(citation_hit=False).citation == "wrong"
    assert only(citations_invalid=["K9:9"]).citation == "wrong"
    assert only(refused=True).citation == "false_refusal"


def test_out_of_scope_questions_have_no_retrieval_and_report_the_refusal() -> None:
    oos = {"should_refuse": True, "expected": [], "category": "out_of_scope", "numbers_total": 0}
    refused = only(**oos, refused=True)
    assert (refused.retrieval, refused.citation, refused.numbers) == ("na", "refused_ok", "na")
    answered = only(**oos, refused=False)
    assert answered.citation == "answered_out_of_scope"


def test_numbers_states() -> None:
    assert only().numbers == "ok"
    assert only(numbers_unmatched=["三千元"]).numbers == "mismatch"
    assert only(numbers_total=0).numbers == "na"
    assert only(refused=True).numbers == "na"


def test_report_carries_metrics_header_and_top_articles() -> None:
    report = build_report(raw(row()))
    assert report.name == "test-run" and report.data_version == "2000-01-01"
    assert report.metrics.number_accuracy is None and report.metrics.mrr == 0.8
    assert report.questions[0].retrieved[0].score == 0.91


def test_old_results_without_scores_still_build() -> None:
    legacy = row()
    del legacy["retrieved_top"]
    assert build_report(raw(legacy)).questions[0].retrieved == []


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(raw(row()), ensure_ascii=False), encoding="utf-8")
    app.dependency_overrides[get_eval_path] = lambda: path
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_serves_the_published_report(client: TestClient) -> None:
    body = client.get("/api/eval/latest").json()
    assert body["counts"]["verified"] == 1
    assert body["questions"][0]["retrieval"] == "hit"
    assert body["metrics"]["recall_at_5"] == 1.0


def test_api_is_404_when_nothing_is_published(tmp_path: Path) -> None:
    app.dependency_overrides[get_eval_path] = lambda: tmp_path / "missing.json"
    try:
        res = TestClient(app).get("/api/eval/latest")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 404 and res.json()["detail"]
