"""把 eval/results 的原始評估結果整理成評估頁要顯示的樣子。"""

from typing import Any

from app.schemas.eval import (
    Citation,
    EvalCounts,
    EvalMetrics,
    EvalReport,
    EvalRetrievedItem,
    EvalRow,
    Numbers,
    Retrieval,
)


def _retrieval(row: dict[str, Any]) -> tuple[Retrieval, int | None]:
    if row["should_refuse"]:
        return "na", None
    recall = row["recall_at_5"]
    rr = row["reciprocal_rank"]
    rank = round(1 / rr) if rr else None
    if recall >= 1:
        return "hit", rank
    return ("partial" if recall > 0 else "miss"), rank


def _citation(row: dict[str, Any]) -> Citation:
    if row["should_refuse"]:
        return "refused_ok" if row["refused"] else "answered_out_of_scope"
    if row["refused"]:
        return "false_refusal"
    return "ok" if row["citation_hit"] and not row["citations_invalid"] else "wrong"


def _numbers(row: dict[str, Any]) -> Numbers:
    if row["refused"] or row["numbers_total"] == 0:
        return "na"
    return "mismatch" if row["numbers_unmatched"] else "ok"


def build_report(raw: dict[str, Any]) -> EvalReport:
    rows = []
    for q in raw["questions"]:
        retrieval, rank = _retrieval(q)
        rows.append(
            EvalRow(
                id=q["id"],
                question=q["question"],
                category=q["category"],
                should_refuse=q["should_refuse"],
                expected=q["expected"],
                retrieved=[EvalRetrievedItem(**item) for item in q.get("retrieved_top", [])],
                retrieval=retrieval,
                first_hit_rank=rank,
                citation=_citation(q),
                numbers=_numbers(q),
                fact_amounts_expected=q.get("fact_amounts_expected"),
                fact_amounts_found=q.get("fact_amounts_found"),
            )
        )
    m = raw["metrics"]
    return EvalReport(
        name=raw["name"],
        evaluated_at=raw["evaluated_at"],
        data_version=raw["config"]["data_version"],
        counts=EvalCounts(**raw["counts"]),
        metrics=EvalMetrics(
            recall_at_5=m["recall_at_5"],
            mrr=m["mrr"],
            citation_accuracy=m["citation_accuracy"],
            number_accuracy=m["number_accuracy"],
            refusal_accuracy=m["refusal_accuracy"],
        ),
        questions=rows,
    )
