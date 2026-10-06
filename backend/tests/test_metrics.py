import pytest

from app.schemas.retrieval import RetrievedChunk
from eval.dataset import EvalQuestion
from eval.metrics import score_question
from eval.run_eval import evaluate


def test_perfect_first_hit() -> None:
    s = score_question(["A"], ["A", "B", "C"])
    assert (s.recall_at_k, s.reciprocal_rank, s.first_hit_rank) == (1.0, 1.0, 1)


def test_second_rank_gives_half_mrr() -> None:
    s = score_question(["A"], ["B", "A", "C"])
    assert s.reciprocal_rank == 0.5 and s.first_hit_rank == 2


def test_miss_scores_zero() -> None:
    s = score_question(["A"], ["B", "C"])
    assert (s.recall_at_k, s.reciprocal_rank, s.first_hit_rank) == (0.0, 0.0, None)


def test_recall_is_fraction_of_expected_found_in_top_k() -> None:
    s = score_question(["A", "B"], ["A", "X", "Y", "Z", "W", "B"], recall_k=5)
    assert s.recall_at_k == 0.5  # B 在第 6 名，不在前 5
    assert s.reciprocal_rank == 1.0  # 但 MRR 看第一個命中


def test_hit_beyond_k_counts_for_mrr_but_not_recall() -> None:
    s = score_question(["A"], ["x1", "x2", "x3", "x4", "x5", "A"], recall_k=5)
    assert s.recall_at_k == 0.0
    assert s.reciprocal_rank == pytest.approx(1 / 6)


def test_empty_expected_is_rejected() -> None:
    with pytest.raises(ValueError):
        score_question([], ["A"])


def hit(rank: int, article_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        rank=rank,
        score=score,
        chunk_id=article_id,
        article_id=article_id,
        pcode="T",
        law_short_name="測",
        article_no=article_id.split(":")[1],
        text="",
    )


def question(
    qid: str,
    expected: list[str],
    *,
    refuse: bool = False,
    verified: bool = True,
    category: str = "fine_amount",
) -> EvalQuestion:
    return EvalQuestion(
        id=qid,
        question=f"問題{qid}",
        category=category,
        expected_chunk_ids=expected,
        expected_facts=[] if refuse else ["x"],
        should_refuse=refuse,
        verified=verified,
    )


def test_evaluate_aggregates_and_skips_unverified_and_out_of_scope() -> None:
    results = {
        "問題q1": [hit(1, "T:1", 0.9), hit(2, "T:2", 0.5)],
        "問題q2": [hit(1, "T:9", 0.8), hit(2, "T:2", 0.7)],
        "問題q4": [hit(1, "T:7", 0.3)],
    }
    qs = [
        question("q1", ["T:1"]),
        question("q2", ["T:2"], category="definition"),
        question("q3", ["T:3"], verified=False),  # 未驗證：不計入
        question("q4", [], refuse=True, category="out_of_scope"),  # 範圍外：不計 Recall/MRR
    ]
    out = evaluate(qs, lambda text, k: results[text])
    assert out["counts"] == {"total": 4, "verified": 3, "answerable": 2, "out_of_scope": 1}
    assert out["metrics"]["recall_at_5"] == 1.0
    assert out["metrics"]["mrr"] == 0.75  # (1 + 0.5) / 2
    assert out["by_category"]["definition"] == {"n": 1, "recall_at_5": 1.0, "mrr": 0.5}
    assert out["score_distribution"]["out_of_scope_top1"] == {"min": 0.3, "max": 0.3}
    assert {q["id"] for q in out["questions"]} == {"q1", "q2", "q4"}
