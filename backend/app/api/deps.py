"""API 的相依物件。真實的相依（索引、模型客戶端）在第一次用到時才建立，
所以 /api/health 不需要金鑰或索引；測試用 app.dependency_overrides 換成假的。"""

from functools import lru_cache

import chromadb
from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.core.embedder import EmbeddingError
from app.core.llm import AnthropicLLMClient, LLMError
from app.core.rate_limit import RateLimiter
from app.ingestion.build_index import COLLECTION
from app.pipeline.articles import ChromaArticleSource, ChromaChunkStore
from app.pipeline.ask_stream import AskDeps
from app.pipeline.retrieve import Retriever


@lru_cache
def _collection() -> chromadb.Collection:
    settings = get_settings()
    return chromadb.PersistentClient(path=str(settings.index_dir)).get_collection(COLLECTION)


def get_ask_deps() -> AskDeps:
    try:
        return _build_ask_deps()
    except (EmbeddingError, LLMError, ValueError, chromadb.errors.ChromaError) as e:
        raise HTTPException(status_code=503, detail="服務尚未就緒（索引或金鑰未設定）") from e


@lru_cache
def _build_ask_deps() -> AskDeps:
    settings = get_settings()
    # 線上不寫磁碟快取：多個請求同時寫同一個檔案會互相覆蓋，也不該把使用者的問題落地
    retriever = Retriever.from_settings(disk_cache=False)
    return AskDeps(
        searcher=retriever,
        articles=ChromaArticleSource(_collection()),
        llm=AnthropicLLMClient(
            settings.anthropic_api_key, settings.llm_model, settings.llm_use_fallbacks
        ),
        gate_threshold=settings.gate_threshold,
        rewrite_enabled=settings.rewrite_enabled,
    )


def get_chunk_store() -> ChromaChunkStore:
    try:
        return ChromaChunkStore(_collection(), ChromaArticleSource(_collection()))
    except (ValueError, chromadb.errors.ChromaError) as e:
        raise HTTPException(status_code=503, detail="索引尚未建立") from e


@lru_cache
def get_rate_limiter() -> RateLimiter:
    settings = get_settings()
    return RateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)


def client_key(request: Request) -> str:
    """速率限制用的來源識別。

    只有明確設定 TRUST_PROXY（部署在自己的反向代理後面）才讀 X-Forwarded-For，並取最後一個值：
    那是我們的代理加上去的；前面的值是用戶端自己填的，可以偽造。
    """
    if get_settings().trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
