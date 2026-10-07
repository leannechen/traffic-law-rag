"""生成：組 prompt、呼叫模型、解析引用標記與拒答標記。"""

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.llm import LLMClient, LLMResponse
from app.pipeline.articles import ArticleText

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
REFUSAL_MARKER = "[[REFUSE]]"
CITATION_RE = re.compile(r"\[\[([^\[\]\n]+?)\]\]")
MAX_TOKENS = 8000


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def build_user_prompt(question: str, articles_in_context: list[ArticleText]) -> str:
    articles = "\n".join(
        f'<條文 id="{a.article_id}" 出處="{a.law_short_name} 第 {a.article_no} 條">'
        f"\n{a.text}\n</條文>"
        for a in articles_in_context
    )
    return f"<條文列表>\n{articles}\n</條文列表>\n\n<問題>\n{question}\n</問題>"


@dataclass(frozen=True)
class ParsedAnswer:
    text: str  # 模型輸出（保留 [[id]] 標記；拒答標記已移除）
    citations: list[str]  # 依出現順序、去重
    refused: bool


def parse_answer(raw: str) -> ParsedAnswer:
    refused = REFUSAL_MARKER in raw
    text = raw.replace(REFUSAL_MARKER, "").strip()
    cited = [m for m in CITATION_RE.findall(text)]
    return ParsedAnswer(text=text, citations=list(dict.fromkeys(cited)), refused=refused)


@dataclass(frozen=True)
class Generation:
    answer: ParsedAnswer
    response: LLMResponse


def generate_answer(llm: LLMClient, question: str, articles: list[ArticleText]) -> Generation:
    response = llm.complete(
        system=load_prompt("generate.md"),
        user=build_user_prompt(question, articles),
        max_tokens=MAX_TOKENS,
        effort="medium",
    )
    if response.refused:  # 安全機制拒絕（含 fallback 也被拒）：視為模型拒答，不當作答案
        return Generation(ParsedAnswer(text="", citations=[], refused=True), response)
    return Generation(parse_answer(response.text), response)
