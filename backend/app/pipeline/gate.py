"""相關度門檻：第一道粗篩。純函式。

單一相似度門檻無法分開貼近主題的範圍外問題（ADR 0004），所以它只負責擋掉明顯無關的問題，
其餘交給模型的拒答標記（第二層）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GateResult:
    passed: bool
    top_score: float | None
    threshold: float


def check_gate(top_score: float | None, threshold: float) -> GateResult:
    """top_score 是原始問題的第一名餘弦相似度；沒有任何檢索結果視為不通過。"""
    return GateResult(
        passed=top_score is not None and top_score >= threshold,
        top_score=top_score,
        threshold=threshold,
    )
