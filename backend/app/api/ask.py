import asyncio
import contextlib
from collections.abc import AsyncIterator, Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.api.deps import client_key, get_ask_deps, get_rate_limiter
from app.core.rate_limit import RateLimiter
from app.pipeline.ask_stream import AskDeps, run_ask
from app.schemas.events import Event, to_sse

router = APIRouter()

MAX_QUESTION_CHARS = 200
HEARTBEAT_SECONDS = 15.0  # 模型思考時可能很久沒有事件，送註解行避免中間的代理關掉閒置連線

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",  # no-transform：不要讓中間的代理壓縮或改寫
    "X-Accel-Buffering": "no",  # 叫 nginx 不要緩衝，否則事件會等到最後才一起送出
}


class AskRequest(BaseModel):
    question: str

    @field_validator("question", mode="before")
    @classmethod
    def strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value  # 長度以去掉頭尾空白後計

    @field_validator("question")
    @classmethod
    def check_length(cls, value: str) -> str:
        if not value:
            raise ValueError("問題不能是空白")
        if len(value) > MAX_QUESTION_CHARS:
            raise ValueError(f"問題不能超過 {MAX_QUESTION_CHARS} 字")
        return value


async def _event_stream(
    request: Request, events: Generator[Event, None, None]
) -> AsyncIterator[str]:
    """把同步的事件產生器接成 SSE：在執行緒池逐個取事件（不阻塞事件迴圈），
    等太久就送心跳，使用者斷線就關閉產生器（連帶關閉對模型的串流，停止計費）。"""
    task: asyncio.Future[Event | None] | None = None
    try:
        while True:
            task = asyncio.ensure_future(run_in_threadpool(next, events, None))
            while True:
                done, _ = await asyncio.wait({task}, timeout=HEARTBEAT_SECONDS)
                if done:
                    break
                yield ": keep-alive\n\n"
            event = task.result()
            if event is None:
                return
            yield to_sse(event)
            if await request.is_disconnected():
                return
    finally:
        if task is not None and not task.done():
            with contextlib.suppress(Exception):
                await asyncio.wait({task})  # 等正在執行的那一步結束，才能關閉產生器
        events.close()


@router.post("/ask")
async def ask(
    body: AskRequest,
    request: Request,
    deps: Annotated[AskDeps, Depends(get_ask_deps)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> StreamingResponse:
    retry_after = limiter.check(client_key(request))
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="請求太頻繁，請稍後再試",
            headers={"Retry-After": str(retry_after)},
        )
    events = run_ask(body.question, deps)
    return StreamingResponse(
        _event_stream(request, events),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
