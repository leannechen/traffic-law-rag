from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, meta
from app.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="Traffic Law RAG")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(meta.router, prefix="/api")
    return app


app = create_app()
