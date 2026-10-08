# 開發用（docker compose）：只有後端；索引用 volume 掛進來。部署用的是根目錄的 Dockerfile。
# 在 repo 根目錄建置（compose 已設定 context: .）。
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# 目錄結構與 repo 相同，config.py 的 REPO_ROOT 才會指到 /app
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY backend/eval/results/latest.json ./eval/results/latest.json
ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
