"""問題改寫：口語 → 1～3 個法律用語查詢。"""

import json

from app.core.llm import LLMClient
from app.pipeline.generate import load_prompt

MAX_QUERIES = 3
SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["queries"],
    "additionalProperties": False,
}


def rewrite_question(llm: LLMClient, question: str) -> tuple[list[str], int, int]:
    """回傳 (查詢清單, 輸入 token, 輸出 token)。原始問題永遠排第一，改寫只是「加上」。

    改寫失敗（拒絕、格式錯誤、空結果）時退回只用原始問題，不讓整個流程失敗。
    """
    response = llm.complete(
        system=load_prompt("rewrite.md"),
        user=question,
        max_tokens=4000,
        effort="low",
        json_schema=SCHEMA,
    )
    queries = [question]
    if not response.refused:
        try:
            rewritten = json.loads(response.text).get("queries", [])
        except (json.JSONDecodeError, AttributeError):
            rewritten = []
        if not isinstance(rewritten, list):
            rewritten = []
        added = 0
        for q in rewritten:
            if added == MAX_QUERIES:
                break
            if isinstance(q, str) and q.strip() and q.strip() not in queries:
                queries.append(q.strip())
                added += 1
    return queries, response.input_tokens, response.output_tokens
