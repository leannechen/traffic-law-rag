# 部署用單一映像：前端建置檔由後端一併提供（ADR 0007）。
# 在 repo 根目錄建置：docker build -t traffic-law-rag .
# 建置前要先有 data/index/（uv run python -m app.ingestion.build_index）。

FROM node:24-slim AS frontend
RUN corepack enable
WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
RUN pnpm exec vite build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# 目錄結構刻意與 repo 相同（/app/backend、/app/data），config.py 的 REPO_ROOT 才會指到 /app
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
# 預先編譯 .pyc：Fly 機器每次停機後檔案系統會重置，沒有 .pyc 的話每次冷啟動都要重新編譯所有套件
RUN UV_COMPILE_BYTECODE=1 uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY backend/eval/results/latest.json ./eval/results/latest.json
COPY data/index /app/data/index
COPY --from=frontend /frontend/dist /app/static
ENV PATH="/app/backend/.venv/bin:$PATH" \
    STATIC_DIR=/app/static \
    TRUST_PROXY=true
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
