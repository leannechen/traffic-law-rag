"""檢索指標。以「條」（article_id）為單位。"""

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionScore:
    recall_at_k: float  # 前 k 名中找到的標準答案條數 / 標準答案條數
    reciprocal_rank: float  # 第一個標準答案的名次倒數；沒找到為 0
    first_hit_rank: int | None


def score_question(expected: list[str], retrieved: list[str], recall_k: int = 5) -> QuestionScore:
    """expected、retrieved 都是 article_id；retrieved 依名次排列、已去重。"""
    if not expected:
        raise ValueError("標準答案為空（範圍外題目不計 Recall／MRR）")
    top = retrieved[:recall_k]
    recall = sum(1 for e in expected if e in top) / len(expected)
    first = next((i for i, a in enumerate(retrieved, start=1) if a in expected), None)
    return QuestionScore(recall, 1 / first if first else 0.0, first)


def mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0
