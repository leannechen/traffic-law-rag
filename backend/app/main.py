from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ask, chunks, eval, health, meta
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.static import mount_frontend


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Traffic Law RAG")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST"],
        expose_headers=["Retry-After"],  # 讓前端的 fetch 讀得到倒數秒數
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(meta.router, prefix="/api")
    app.include_router(ask.router, prefix="/api")
    app.include_router(chunks.router, prefix="/api")
    app.include_router(eval.router, prefix="/api")
    static_dir = get_settings().static_dir
    if static_dir is not None:
        mount_frontend(app, static_dir)  # 必須最後掛，才不會蓋掉 /api
    return app


app = create_app()
