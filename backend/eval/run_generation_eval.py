"""評估完整問答（生成、引用、數字、拒答）。需要 ANTHROPIC_API_KEY 與 VOYAGE_API_KEY。

    uv run python -m eval.run_generation_eval --name gen-sonnet-norewrite
    uv run python -m eval.run_generation_eval --name gen-sonnet-rewrite --rewrite
    uv run python -m eval.run_generation_eval --name x --refresh   # 忽略 LLM 快取，重新呼叫
    uv run python -m eval.run_generation_eval --name x --publish   # 同時發布成 latest.json

LLM 的回應存在 data/cache/llm_responses.json（不進版控）：prompt 與參數不變就不會重複呼叫，
結果可重現也不花錢。改了 prompt 或模型，快取鍵自然不同，會重新呼叫。
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.llm import AnthropicLLMClient, CachedLLMClient
from app.ingestion.build_index import META_FILE
from app.pipeline.answer import CONTEXT_K, AnswerResult, answer_question
from app.pipeline.articles import ChromaArticleSource
from app.pipeline.generate import PROMPTS_DIR
from app.pipeline.retrieve import Retriever
from eval.dataset import load_dataset
from eval.gen_eval import evaluate_generation
from eval.run_eval import RESULTS_DIR

PUBLISHED_NAME = "latest.json"

# 估算費用用（USD／百萬 token）。僅供參考，實際以帳單為準。
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}


def prompt_version() -> str:
    text = "".join(
        (PROMPTS_DIR / n).read_text(encoding="utf-8") for n in ("generate.md", "rewrite.md")
    )
    return hashlib.sha256(text.encode()).hexdigest()[:10]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--rewrite", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="同時寫成 eval/results/latest.json，評估頁（/api/eval/latest）顯示的就是這份",
    )
    args = parser.parse_args()

    settings = get_settings()
    inner = AnthropicLLMClient(
        settings.anthropic_api_key, settings.llm_model, settings.llm_use_fallbacks
    )
    llm = CachedLLMClient(inner, settings.cache_dir / "llm_responses.json", refresh=args.refresh)
    searcher = Retriever.from_settings()
    articles = ChromaArticleSource(searcher._collection)
    index_meta = json.loads((settings.index_dir / META_FILE).read_text(encoding="utf-8"))

    def pipeline(question: str) -> AnswerResult:
        return answer_question(
            question,
            searcher=searcher,
            articles=articles,
            llm=llm,
            threshold=settings.gate_threshold,
            rewrite=args.rewrite,
        )

    result = evaluate_generation(load_dataset(), pipeline)
    tokens = result["metrics"]["tokens"]
    price = PRICES.get(settings.llm_model)
    # 快取命中的回應不會再花錢，但 token 數仍計入（代表「第一次跑」的花費）
    cost = (tokens["input"] * price[0] + tokens["output"] * price[1]) / 1e6 if price else None
    out: dict[str, Any] = {
        "name": args.name,
        "evaluated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "config": {
            "llm_model": settings.llm_model,
            "rewrite": args.rewrite,
            "gate_threshold": settings.gate_threshold,
            "context_k": CONTEXT_K,
            "prompt_version": prompt_version(),
            "embedding_model": index_meta["embedding_model"],
            "data_version": index_meta["data_version"],
            "llm_calls": llm.calls,
            "llm_cache_hits": llm.cache_hits,
            "estimated_cost_usd_first_run": round(cost, 3) if cost is not None else None,
        },
        **result,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{args.name}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.publish:
        (RESULTS_DIR / PUBLISHED_NAME).write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    print_summary(out)
    print(f"\n已寫入 {path}" + (f" 並發布為 {PUBLISHED_NAME}" if args.publish else ""))


def print_summary(r: dict[str, Any]) -> None:
    c, m, cfg = r["counts"], r["metrics"], r["config"]
    rewrite = "開" if cfg["rewrite"] else "關"
    na = m["number_accuracy"]
    na_text = "無" if na is None else f"{na:.3f}"
    lines = [
        f"模型 {cfg['llm_model']}｜改寫 {rewrite}｜門檻 {cfg['gate_threshold']}",
        f"prompt 版本 {cfg['prompt_version']}",
        f"LLM 呼叫 {cfg['llm_calls']} 次（快取命中 {cfg['llm_cache_hits']} 次）",
        f"題數：{c['verified']}（可回答 {c['answerable']}、範圍外 {c['out_of_scope']}）",
        "",
        f"1. Recall@5            {m['recall_at_5']:.3f}",
        f"2. MRR                 {m['mrr']:.3f}",
        f"3. 引用正確率          {m['citation_accuracy']:.3f}",
        f"     已作答題目中 {m['citation_accuracy_answered']:.3f}",
        f"     引用精確率 {m['citation_precision']}（引用的條文中屬於標準答案的比例）",
        f"     無效引用 {m['invalid_citations']} 個",
        f"4. 數字正確率          {na_text}",
        f"     答案數字全對的比例 {m['answers_all_numbers_ok']:.3f}",
        f"     重點金額涵蓋率 {m['fact_amount_coverage']}",
        f"5. 拒答正確率          {m['refusal_accuracy']:.3f}",
        f"     範圍外拒答 {m['out_of_scope_refused']} {m['out_of_scope_refused_by_layer']}",
        f"     誤拒 {m['false_refusals']} {m['false_refusals_by_layer']}",
        "",
        f"token：{m['tokens']['input']} 輸入／{m['tokens']['output']} 輸出",
        f"首次執行估計費用 US${cfg['estimated_cost_usd_first_run']}",
    ]
    print("\n".join(lines))
    problems = [q for q in r["questions"] if _has_problem(q)]
    print(f"\n需要看的題目（{len(problems)}）：")
    for q in problems:
        print(f"  {q['id']} {'、'.join(_why(q))}｜{q['question']}")


def _why(q: dict[str, Any]) -> list[str]:
    why = []
    if q["should_refuse"] and not q["refused"]:
        why.append("範圍外卻作答")
    if not q["should_refuse"] and q["refused"]:
        why.append(f"誤拒（{q['refusal_layer']}）")
    if q.get("citation_hit") is False and not q["refused"]:
        why.append("沒引用標準答案")
    if q["citations_invalid"]:
        why.append(f"無效引用 {q['citations_invalid']}")
    if q["numbers_unmatched"]:
        why.append(f"數字對不上 {q['numbers_unmatched']}")
    return why


def _has_problem(q: dict[str, Any]) -> bool:
    if q["should_refuse"]:
        return not q["refused"]
    return bool(
        q["refused"] or q["citations_invalid"] or q["numbers_unmatched"] or not q["citation_hit"]
    )


if __name__ == "__main__":
    main()
