"""MCP server（stdio）：讓 Claude Code 直接查交通法規（ADR 0009）。

三個 tool：
- ask_traffic_law：跑與 web 同一套流程（answer_question：檢索 → gate → 生成 → 引用／數字驗證），
  回傳有出處的答案或拒答。
- search_traffic_law／get_article：只做檢索，回傳條文原文，不呼叫 LLM。

註冊：claude mcp add traffic-law -- uv --directory <repo>/backend run python -m app.mcp_server
stdout 是協議通道，任何輸出都要走 stderr（logging 預設就是）。
"""

from collections.abc import Callable
from typing import Annotated, Any, Literal

import chromadb
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.llm import AnthropicLLMClient, Effort, LLMClient, LLMResponse
from app.core.logging import configure_logging
from app.ingestion.build_index import COLLECTION
from app.pipeline.answer import AnswerResult, Searcher, answer_question
from app.pipeline.articles import ArticleSource, ChromaArticleSource
from app.pipeline.retrieve import Retriever

MAX_QUERY_CHARS = 200  # 與 /api/ask 相同
MAX_K = 10

SCOPE = (
    "收錄 5 部法規：道路交通管理處罰條例、道路交通安全規則、道路交通事故處理辦法、"
    "強制汽車責任保險法、違反道路交通管理事件統一裁罰基準及處理細則（只有條文；"
    "裁罰基準的金額附表沒有內容，查不到）。"
)
NOTICE = (
    "score 是餘弦相似度；低於約 0.40 通常表示收錄的法規沒有相關依據，請直接說查不到，"
    "不要用這些條文硬湊答案。回答時引用條號並附 source_url；金額、期間必須逐字出自條文。"
    "本資料不是法律意見，實際罰則請以全國法規資料庫現行條文為準。"
)


class Article(BaseModel):
    article_id: str  # "{pcode}:{article_no}"，可傳給 get_article
    law: str
    article_no: str
    score: float | None = None  # 只有搜尋結果才有
    amended_date: str = ""
    source_url: str = ""
    text: str  # 整條原文


class SearchResult(BaseModel):
    data_version: str
    notice: str
    results: list[Article]


class Citation(BaseModel):
    article_id: str
    law: str
    article_no: str
    source_url: str = ""


class AskOutput(BaseModel):
    data_version: str
    refused: bool
    refusal_layer: Literal["gate", "model"] | None = None
    refusal_message: str = ""
    answer: str = ""  # 答案中的 [[article_id]] 是引用標記，對照 citations
    citations: list[Citation] = []
    citations_invalid: list[str] = []  # 非空表示答案引用了沒提供給模型的條文，不可採信
    numbers_unmatched: list[str] = []  # 答案中在引用條文裡找不到的數字，不可採信
    top_score: float | None = None
    notice: str


ASK_NOTICE = (
    "答案由與網站相同的流程產生並已驗證引用與數字。請原文呈現 answer 與引用的條號，"
    "不要改寫金額或期間；citations_invalid 或 numbers_unmatched 非空時要明確告知使用者。"
    "refused 為 true 時直接說依收錄的法規查不到，不要自行補答案。"
    "本資料不是法律意見，實際罰則請以全國法規資料庫現行條文為準。"
)
REFUSAL_MESSAGES = {
    "gate": "問題與收錄的法規相關度太低，查不到依據。",
    "model": "檢索到的條文不足以回答這個問題。",
}

Asker = Callable[[str], AnswerResult]


class _TruncationGuard:
    """包住 LLM 記下 stop_reason：答案被長度上限截斷時不能當完整答案（web 的 run_ask 同樣處理）。"""

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self.model = inner.model
        self.truncated = False

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        effort: Effort,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        response = self._inner.complete(
            system=system, user=user, max_tokens=max_tokens, effort=effort, json_schema=json_schema
        )
        if response.stop_reason == "max_tokens":
            self.truncated = True
        return response

    def stream(self, **kwargs: Any) -> Any:
        return self._inner.stream(**kwargs)


def make_asker(
    searcher: Searcher,
    articles: ArticleSource,
    llm_factory: Callable[[], LLMClient],
    *,
    threshold: float,
    rewrite: bool = False,
) -> Asker:
    """llm_factory 在第一次提問時才呼叫：沒有 ANTHROPIC_API_KEY 時，檢索 tool 仍可使用。"""

    def ask(question: str) -> AnswerResult:
        guard = _TruncationGuard(llm_factory())
        result = answer_question(
            question,
            searcher=searcher,
            articles=articles,
            llm=guard,
            threshold=threshold,
            rewrite=rewrite,
        )
        if guard.truncated:
            raise ValueError("答案太長，被截斷了。請把問題問得更具體一點。")
        return result

    return ask


def build_server(
    searcher: Searcher,
    articles: ArticleSource,
    data_version: str,
    meta: dict[str, Any],
    ask: Asker,
) -> MCPServer:
    """meta：article_id → 該條的 amended_date／source_url。"""
    mcp = MCPServer("traffic-law")

    @mcp.tool(
        description=(
            "用白話問題查台灣交通法規，回傳有條文出處的答案（與網站同一套流程，已驗證引用與數字）；"
            "條文不足時會拒答。" + SCOPE
        ),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    def ask_traffic_law(
        question: Annotated[str, Field(description="白話問題，最多 200 字")],
    ) -> AskOutput:
        question = question.strip()
        if not question or len(question) > MAX_QUERY_CHARS:
            raise ValueError(f"question 必須是 1–{MAX_QUERY_CHARS} 字")
        result = ask(question)
        if result.refused:
            layer = result.refusal_layer
            return AskOutput(
                data_version=data_version,
                refused=True,
                refusal_layer=layer,
                refusal_message=REFUSAL_MESSAGES.get(layer or "", ""),
                top_score=result.gate_top_score,
                notice=ASK_NOTICE,
            )
        citations = []
        for article_id in result.citations_valid:
            found = articles.get(article_id)
            if found:
                citations.append(
                    Citation(
                        article_id=article_id,
                        law=found.law_short_name,
                        article_no=found.article_no,
                        source_url=meta.get(article_id, {}).get("source_url", ""),
                    )
                )
        return AskOutput(
            data_version=data_version,
            refused=False,
            answer=result.answer,
            citations=citations,
            citations_invalid=result.citations_invalid,
            numbers_unmatched=result.numbers_unmatched,
            top_score=result.gate_top_score,
            notice=ASK_NOTICE,
        )

    @mcp.tool(
        description="用白話問題檢索台灣交通法規條文，回傳整條原文與相似度。" + SCOPE,
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    def search_traffic_law(
        query: Annotated[str, Field(description="白話問題，最多 200 字，例如「紅燈右轉罰多少」")],
        k: Annotated[int, Field(ge=1, le=MAX_K, description="最多回傳幾條")] = 5,
    ) -> SearchResult:
        query = query.strip()
        if not query or len(query) > MAX_QUERY_CHARS:
            raise ValueError(f"query 必須是 1–{MAX_QUERY_CHARS} 字")
        results: list[Article] = []
        for hit in searcher.search(query, k):
            full = articles.get(hit.article_id)
            results.append(
                Article(
                    article_id=hit.article_id,
                    law=hit.law_short_name,
                    article_no=hit.article_no,
                    score=hit.score,
                    amended_date=hit.amended_date,
                    source_url=hit.source_url,
                    text=full.text if full else hit.text,
                )
            )
        return SearchResult(data_version=data_version, notice=NOTICE, results=results)

    @mcp.tool(
        description="依 article_id 取得整條條文原文。" + SCOPE,
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    def get_article(
        article_id: Annotated[
            str, Field(description="例如 K0040012:53（search_traffic_law 回傳）")
        ],
    ) -> Article:
        found = articles.get(article_id)
        if found is None:
            raise ValueError(f"找不到條文：{article_id}")
        extra = meta.get(article_id, {})
        return Article(
            article_id=found.article_id,
            law=found.law_short_name,
            article_no=found.article_no,
            amended_date=extra.get("amended_date", ""),
            source_url=extra.get("source_url", ""),
            text=found.text,
        )

    return mcp


def main() -> None:
    configure_logging()
    collection = chromadb.PersistentClient(path=str(get_settings().index_dir)).get_collection(
        COLLECTION
    )
    got = collection.get(include=["metadatas"])
    metas = got["metadatas"] or []
    meta = {
        f"{m['pcode']}:{m['article_no']}": {
            "amended_date": str(m.get("amended_date", "")),
            "source_url": str(m.get("source_url", "")),
        }
        for m in metas
    }
    data_version = str(metas[0]["data_version"]) if metas else ""
    # 本機使用：問題的 embedding 可以落地快取（與 CLI 一致）
    retriever = Retriever.from_settings(disk_cache=True)
    articles = ChromaArticleSource(collection)
    settings = get_settings()
    ask = make_asker(
        retriever,
        articles,
        lambda: AnthropicLLMClient(
            settings.anthropic_api_key, settings.llm_model, settings.llm_use_fallbacks
        ),
        threshold=settings.gate_threshold,
        rewrite=settings.rewrite_enabled,
    )
    build_server(retriever, articles, data_version, meta, ask).run()


if __name__ == "__main__":
    main()
