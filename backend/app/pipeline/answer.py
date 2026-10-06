"""非串流的完整問答流程（Step 6 再改成串流事件）。

rewrite（可選）→ retrieve → gate → generate → validate
"""

import argparse
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.llm import AnthropicLLMClient, LLMClient
from app.pipeline.gate import GateResult, check_gate
from app.pipeline.generate import generate_answer
from app.pipeline.retrieve import FUSION_DEPTH, Retriever, rrf
from app.pipeline.rewrite import rewrite_question
from app.pipeline.validate import (
    CitationCheck,
    NumberCheck,
    check_numbers,
    validate_citations,
)
from app.schemas.retrieval import RetrievedChunk

CONTEXT_K = 5  # 給模型看的條數
RETRIEVAL_DEPTH = 10  # 檢索指標看前 10 名（與 Step 4 的評估一致）


class Searcher(Protocol):
    def search(self, question: str, k: int = 5) -> list[RetrievedChunk]: ...


def retrieve_multi(
    searcher: Searcher, queries: list[str], depth: int = RETRIEVAL_DEPTH
) -> list[RetrievedChunk]:
    """多個查詢各自檢索，以 RRF 合併（以條為單位）。只有一個查詢時就是原本的結果。

    vector_score 取該條在各查詢中的最高餘弦相似度。
    """
    if len(queries) == 1:
        return searcher.search(queries[0], depth)
    lists = [searcher.search(q, max(depth, FUSION_DEPTH)) for q in queries]
    best: dict[str, RetrievedChunk] = {}
    for hits in lists:
        for h in hits:
            cur = best.get(h.article_id)
            if cur is None or (h.vector_score or 0) > (cur.vector_score or 0):
                best[h.article_id] = h
    fused = rrf([[h.article_id for h in hits] for hits in lists])
    return [
        best[article_id].model_copy(update={"rank": rank, "score": round(score, 5)})
        for rank, (article_id, score) in enumerate(fused[:depth], start=1)
    ]


class AnswerResult(BaseModel):
    question: str
    queries: list[str]
    retrieved: list[RetrievedChunk]  # 檢索結果（前 RETRIEVAL_DEPTH 條）
    gate_passed: bool
    gate_top_score: float | None
    gate_threshold: float
    refused: bool
    refusal_layer: Literal["gate", "model"] | None = None
    answer: str = ""
    citations_valid: list[str] = []
    citations_invalid: list[str] = []
    numbers_total: int = 0
    numbers_matched: int = 0
    numbers_unmatched: list[str] = []
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0


def answer_question(
    question: str,
    *,
    searcher: Searcher,
    llm: LLMClient,
    threshold: float,
    rewrite: bool = False,
) -> AnswerResult:
    usage = _Usage()
    queries = [question]
    if rewrite:
        queries, tin, tout = rewrite_question(llm, question)
        usage.input_tokens += tin
        usage.output_tokens += tout
    retrieved = retrieve_multi(searcher, queries)
    # 門檻看「原始問題」的第一名相似度，讓行為與 Step 4 的分析一致（改寫可能把範圍外問題拉高）
    original = retrieved if len(queries) == 1 else searcher.search(question, 1)
    top_score = original[0].vector_score if original else None
    gate: GateResult = check_gate(top_score, threshold)

    base = dict(
        question=question,
        queries=queries,
        retrieved=retrieved,
        gate_passed=gate.passed,
        gate_top_score=gate.top_score,
        gate_threshold=gate.threshold,
    )
    if not gate.passed:
        return AnswerResult(
            **base,
            refused=True,
            refusal_layer="gate",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )

    context = retrieved[:CONTEXT_K]
    generation = generate_answer(llm, question, context)
    usage.input_tokens += generation.response.input_tokens
    usage.output_tokens += generation.response.output_tokens
    parsed = generation.answer
    if parsed.refused:
        return AnswerResult(
            **base,
            refused=True,
            refusal_layer="model",
            model=generation.response.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )

    citation: CitationCheck = validate_citations(parsed.citations, {c.chunk_id for c in context})
    cited_texts = [c.text for c in context if c.chunk_id in set(citation.valid)]
    numbers: NumberCheck = check_numbers(parsed.text, cited_texts)
    return AnswerResult(
        **base,
        refused=False,
        answer=parsed.text,
        citations_valid=citation.valid,
        citations_invalid=citation.invalid,
        numbers_total=numbers.total,
        numbers_matched=numbers.matched,
        numbers_unmatched=numbers.unmatched,
        model=generation.response.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="問一個問題，印出答案與驗證結果")
    parser.add_argument("question")
    parser.add_argument("--rewrite", action="store_true", help="先改寫問題再檢索")
    args = parser.parse_args()
    settings = get_settings()
    llm = AnthropicLLMClient(
        settings.anthropic_api_key, settings.llm_model, settings.llm_use_fallbacks
    )
    result = answer_question(
        args.question,
        searcher=Retriever.from_settings(),
        llm=llm,
        threshold=settings.gate_threshold,
        rewrite=args.rewrite,
    )
    print(f"查詢：{result.queries}")
    top = f"{result.gate_top_score:.3f}" if result.gate_top_score is not None else "無"
    print(f"門檻：最高相似度 {top}／門檻 {result.gate_threshold}")
    for h in result.retrieved[:CONTEXT_K]:
        print(f"  {h.rank}. {h.chunk_id}（{h.vector_score}）")
    if result.refused:
        print(f"\n【拒答】由「{result.refusal_layer}」擋下")
        return
    print(f"\n{result.answer}\n")
    print(f"引用：有效 {result.citations_valid}／無效 {result.citations_invalid}")
    print(
        f"數字：{result.numbers_matched}/{result.numbers_total} 在引用條文中找到"
        + (f"，找不到：{result.numbers_unmatched}" if result.numbers_unmatched else "")
    )
    print(f"用量：{result.input_tokens} 輸入／{result.output_tokens} 輸出 token（{result.model}）")


if __name__ == "__main__":
    main()
