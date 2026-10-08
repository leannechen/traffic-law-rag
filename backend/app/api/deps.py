"""API 的相依物件。真實的相依（索引、模型客戶端）在第一次用到時才建立，
所以 /api/health 不需要金鑰或索引；測試用 app.dependency_overrides 換成假的。"""

import threading
from functools import lru_cache

import chromadb
from fastapi import HTTPException, Request

from app.core.budget import DailyBudget
from app.core.config import get_settings
from app.core.embedder import EmbeddingError
from app.core.llm import AnthropicLLMClient, LLMError
from app.core.rate_limit import RateLimiter
from app.ingestion.build_index import COLLECTION
from app.pipeline.articles import ChromaArticleSource, ChromaChunkStore
from app.pipeline.ask_stream import AskDeps
from app.pipeline.retrieve import Retriever

# Chroma 的客戶端不能同時建立：兩個執行緒同時第一次開同一個索引，
# 會有一個拿到建到一半的物件而當掉（機器剛喚醒、同時進來兩個請求就會遇到）。
# lru_cache 不擋同時進入，所以在外面加鎖；建好之後只是查快取。
_init_lock = threading.RLock()


def _collection() -> chromadb.Collection:
    with _init_lock:
        return _collection_cached()


@lru_cache
def _collection_cached() -> chromadb.Collection:
    settings = get_settings()
    return chromadb.PersistentClient(path=str(settings.index_dir)).get_collection(COLLECTION)


def get_ask_deps() -> AskDeps:
    try:
        with _init_lock:
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


@lru_cache
def get_daily_budget() -> DailyBudget:
    return DailyBudget(get_settings().daily_ask_limit)


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
