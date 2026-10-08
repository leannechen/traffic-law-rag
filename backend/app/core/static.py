from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """提供前端建置檔；不是檔案的路徑回 index.html，讓 React Router 處理（/eval、/?q=…）。"""
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"STATIC_DIR 底下沒有 index.html：{root}")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)  # 打錯的 API 路徑要是 404，不是一個 HTML 頁
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        if "." in path.rsplit("/", 1)[-1]:
            raise HTTPException(status_code=404)  # 缺的 .js/.css 不能回 HTML
        return FileResponse(index)
