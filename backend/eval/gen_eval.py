"""生成評估：Recall@5、MRR、引用正確率、數字正確率、拒答正確率。純函式（不碰網路）。

指標定義（ADR 0005）：
- 引用正確率 = 有作答、且至少引用一條標準答案（以「條」比對）的題數 ÷ 可回答題數。
  被誤拒的題目算錯；另外單獨回報「已作答題目」的比例與無效引用數。
  這個定義寬鬆（多引用別條不扣分），所以另附「引用精確率」= 引用的條中屬於標準答案的比例。
  引用精確率偏低未必是錯：額外引用的條文可能也相關，需要人工判讀。
- 數字正確率 = 答案中的數量（數字＋單位）能在「它引用的條文」找到的比例（微平均）。
  另附：每個答案的數字全部正確的比例、「重點金額涵蓋率」（expected_facts 的數量有多少出現在答案）。
- 拒答正確率 = (範圍外題有拒答 + 可回答題有作答) ÷ 全部題數；並分開回報兩個成分與擋下的層級。
"""

from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Any

from app.pipeline.answer import AnswerResult
from app.pipeline.validate import extract_quantities
from eval.dataset import EvalQuestion
from eval.metrics import mean, score_question

RECALL_K = 5


def article_of(chunk_id: str) -> str:
    return chunk_id.split("-p")[0]


def _round(value: float) -> float:
    return round(value, 4)


def evaluate_generation(
    questions: list[EvalQuestion], pipeline: Callable[[str], AnswerResult]
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for q in (q for q in questions if q.verified):
        result = pipeline(q.question)
        row: dict[str, Any] = {
            "id": q.id,
            "question": q.question,
            "category": q.category,
            "should_refuse": q.should_refuse,
            "expected": q.expected_chunk_ids,
            "queries": result.queries,
            "retrieved": [h.article_id for h in result.retrieved],
            "gate_top_score": result.gate_top_score,
            "refused": result.refused,
            "refusal_layer": result.refusal_layer,
            "answer": result.answer,
            "citations_valid": result.citations_valid,
            "citations_invalid": result.citations_invalid,
            "numbers_total": result.numbers_total,
            "numbers_matched": result.numbers_matched,
            "numbers_unmatched": result.numbers_unmatched,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
        if not q.should_refuse:
            s = score_question(q.expected_chunk_ids, row["retrieved"], RECALL_K)
            row.update(recall_at_5=s.recall_at_k, reciprocal_rank=s.reciprocal_rank)
            cited = {article_of(c) for c in result.citations_valid}
            row["citation_hit"] = (not result.refused) and bool(cited & set(q.expected_chunk_ids))
            row["citations_cited"] = len(cited)
            row["citations_in_expected"] = len(cited & set(q.expected_chunk_ids))
            if not result.refused:
                wanted = set(extract_quantities(" ".join(q.expected_facts)))
                got = set(extract_quantities(result.answer))
                row["fact_amounts_expected"] = len(wanted)
                row["fact_amounts_found"] = len(wanted & got)
        rows.append(row)
    return {"counts": _counts(rows), "metrics": _metrics(rows), "questions": rows}


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "verified": len(rows),
        "answerable": sum(not r["should_refuse"] for r in rows),
        "out_of_scope": sum(r["should_refuse"] for r in rows),
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [r for r in rows if not r["should_refuse"]]
    oos = [r for r in rows if r["should_refuse"]]
    answered = [r for r in answerable if not r["refused"]]

    num_total = sum(r["numbers_total"] for r in answered)
    num_matched = sum(r["numbers_matched"] for r in answered)
    facts_expected = sum(r.get("fact_amounts_expected", 0) for r in answered)
    facts_found = sum(r.get("fact_amounts_found", 0) for r in answered)
    layer = Counter(r["refusal_layer"] for r in oos if r["refused"])
    false_layer = Counter(r["refusal_layer"] for r in answerable if r["refused"])

    by_category: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in answerable:
        groups[r["category"]].append(r)
    for category, rs in groups.items():
        by_category[category] = {
            "n": len(rs),
            "citation_accuracy": _round(mean([1.0 if r["citation_hit"] else 0.0 for r in rs])),
            "refused": sum(r["refused"] for r in rs),
        }

    cited_ok = sum(r["citations_in_expected"] for r in answered)
    correct_refusal = sum(r["refused"] for r in oos) + len(answered)
    return {
        "recall_at_5": _round(mean([r["recall_at_5"] for r in answerable])),
        "mrr": _round(mean([r["reciprocal_rank"] for r in answerable])),
        "citation_accuracy": _round(mean([1.0 if r["citation_hit"] else 0.0 for r in answerable])),
        "citation_accuracy_answered": _round(
            mean([1.0 if r["citation_hit"] else 0.0 for r in answered])
        ),
        "citation_precision": (
            _round(cited_ok / cited_all)
            if (cited_all := sum(r["citations_cited"] for r in answered))
            else None
        ),
        "invalid_citations": sum(len(r["citations_invalid"]) for r in answered),
        "answers_with_invalid_citation": sum(bool(r["citations_invalid"]) for r in answered),
        "number_accuracy": _round(num_matched / num_total) if num_total else None,
        "answers_all_numbers_ok": _round(
            mean([0.0 if r["numbers_unmatched"] else 1.0 for r in answered])
        ),
        "fact_amount_coverage": _round(facts_found / facts_expected) if facts_expected else None,
        "refusal_accuracy": _round(correct_refusal / len(rows)) if rows else 0.0,
        "out_of_scope_refused": f"{sum(r['refused'] for r in oos)}/{len(oos)}",
        "out_of_scope_refused_by_layer": dict(layer),
        "false_refusals": f"{sum(r['refused'] for r in answerable)}/{len(answerable)}",
        "false_refusals_by_layer": dict(false_layer),
        "tokens": {
            "input": sum(r["input_tokens"] for r in rows),
            "output": sum(r["output_tokens"] for r in rows),
        },
        "by_category": by_category,
    }
