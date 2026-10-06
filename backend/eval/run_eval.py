"""評估檢索品質：Recall@5、MRR。只計入 verified: true 的題目。

    uv run python -m eval.run_eval                      # 寫入 eval/results/latest.json
    uv run python -m eval.run_eval --name baseline-vector  # 寫入 eval/results/baseline-vector.json
    uv run python -m eval.run_eval --retriever hybrid --name hybrid-jieba

範圍外題目（should_refuse）不計 Recall／MRR，改記錄它們的最高分，供之後訂拒答門檻。
"""

import argparse
import json
import statistics
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.ingestion.build_index import META_FILE
from app.ingestion.chunk import MAX_CHARS
from app.pipeline.retrieve import HybridRetriever, Retriever
from app.schemas.retrieval import RetrievedChunk
from eval.dataset import EvalQuestion, load_dataset
from eval.metrics import mean, score_question

RESULTS_DIR = Path(__file__).with_name("results")
RECALL_K = 5
DEPTH = 10  # 取回深度；Recall@5 看前 5 名，MRR 看前 10 名

Search = Callable[[str, int], list[RetrievedChunk]]


def top_vector_score(hits: list[RetrievedChunk]) -> float | None:
    """回傳結果中最高的餘弦相似度（供拒答門檻參考）。hybrid 的 score 是 RRF 分數，不能比較。"""
    scores = [h.vector_score for h in hits if h.vector_score is not None]
    return max(scores) if scores else None


def evaluate(questions: list[EvalQuestion], search: Search) -> dict[str, Any]:
    verified = [q for q in questions if q.verified]
    per_question: list[dict[str, Any]] = []
    for q in verified:
        hits = search(q.question, DEPTH)
        row: dict[str, Any] = {
            "id": q.id,
            "question": q.question,
            "category": q.category,
            "should_refuse": q.should_refuse,
            "expected": q.expected_chunk_ids,
            "retrieved": [
                {
                    "rank": h.rank,
                    "article_id": h.article_id,
                    "chunk_id": h.chunk_id,
                    "score": h.score,
                    "vector_score": h.vector_score,
                }
                for h in hits
            ],
            "top_score": top_vector_score(hits),
        }
        if not q.should_refuse:
            s = score_question(q.expected_chunk_ids, [h.article_id for h in hits], RECALL_K)
            row.update(
                recall_at_5=s.recall_at_k,
                reciprocal_rank=s.reciprocal_rank,
                first_hit_rank=s.first_hit_rank,
            )
        per_question.append(row)

    answerable = [r for r in per_question if not r["should_refuse"]]
    refusals = [r for r in per_question if r["should_refuse"]]
    by_category: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in answerable:
        groups[r["category"]].append(r)
    for category, rows in groups.items():
        by_category[category] = {
            "n": len(rows),
            "recall_at_5": round(mean([r["recall_at_5"] for r in rows]), 4),
            "mrr": round(mean([r["reciprocal_rank"] for r in rows]), 4),
        }
    answerable_top = [r["top_score"] for r in answerable if r["top_score"] is not None]
    refusal_top = [r["top_score"] for r in refusals if r["top_score"] is not None]
    return {
        "counts": {
            "total": len(questions),
            "verified": len(verified),
            "answerable": len(answerable),
            "out_of_scope": len(refusals),
        },
        "metrics": {
            "recall_at_5": round(mean([r["recall_at_5"] for r in answerable]), 4),
            "mrr": round(mean([r["reciprocal_rank"] for r in answerable]), 4),
            "hit_rate_at_5": round(
                mean([1.0 if (r["first_hit_rank"] or 99) <= RECALL_K else 0.0 for r in answerable]),
                4,
            ),
        },
        "by_category": by_category,
        "score_distribution": {
            "answerable_top1": {
                "min": min(answerable_top, default=None),
                "median": statistics.median(answerable_top) if answerable_top else None,
                "max": max(answerable_top, default=None),
            },
            "out_of_scope_top1": {
                "min": min(refusal_top, default=None),
                "max": max(refusal_top, default=None),
            },
        },
        "questions": per_question,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="latest", help="輸出檔名（不含副檔名）")
    parser.add_argument(
        "--retriever", choices=["vector", "hybrid", "hybrid-bigram"], default="vector"
    )
    args = parser.parse_args()

    settings = get_settings()
    index_meta = json.loads((settings.index_dir / META_FILE).read_text(encoding="utf-8"))
    retriever: Retriever | HybridRetriever = (
        Retriever.from_settings()
        if args.retriever == "vector"
        else HybridRetriever.from_settings(
            "bigram" if args.retriever.endswith("bigram") else "jieba"
        )
    )
    result = evaluate(load_dataset(), retriever.search)
    result = {
        "name": args.name,
        "retriever": args.retriever,
        "evaluated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "config": {
            "embedding_model": index_meta["embedding_model"],
            "data_version": index_meta["data_version"],
            "chunk_count": index_meta["chunk_count"],
            "chunk_max_chars": MAX_CHARS,
            "recall_k": RECALL_K,
            "retrieval_depth": DEPTH,
            "unit": "article",
        },
        **result,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{args.name}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(result)
    print(f"\n已寫入 {out}")


def print_summary(r: dict[str, Any]) -> None:
    c, m = r["counts"], r["metrics"]
    print(
        f"題數：{c['verified']} 題已驗證"
        f"（{c['answerable']} 題可回答、{c['out_of_scope']} 題範圍外）"
    )
    print(
        f"Recall@5 = {m['recall_at_5']:.3f}　MRR = {m['mrr']:.3f}　"
        f"命中率@5 = {m['hit_rate_at_5']:.3f}"
    )
    print(f"\n{'類別':14} {'題數':>4} {'Recall@5':>9} {'MRR':>6}")
    for category, v in r["by_category"].items():
        print(f"{category:14} {v['n']:>4} {v['recall_at_5']:>9.3f} {v['mrr']:>6.3f}")
    d = r["score_distribution"]
    a, o = d["answerable_top1"], d["out_of_scope_top1"]
    print(
        f"\n第一名相似度：可回答題 {a['min']}–{a['max']}（中位 {a['median']}）；"
        f"範圍外題 {o['min']}–{o['max']}"
    )
    misses = [
        q for q in r["questions"] if not q["should_refuse"] and (q["first_hit_rank"] or 99) > 1
    ]
    print(f"\n第一名不是標準答案的題目（{len(misses)} 題）：")
    for q in misses:
        got = [h["article_id"] for h in q["retrieved"][:3]]
        print(f"  {q['id']} 命中名次={q['first_hit_rank']}　期望={q['expected']}　前三={got}")


if __name__ == "__main__":
    main()
