import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.pipeline.eval_report import build_report
from app.schemas.eval import EvalReport

router = APIRouter()


def get_eval_path() -> Path:
    return get_settings().eval_latest_path


@router.get("/eval/latest")
def latest_eval(path: Annotated[Path, Depends(get_eval_path)]) -> EvalReport:
    """評估頁顯示的那一份結果（run_generation_eval --publish 產生的 latest.json）。"""
    if not path.exists():
        raise HTTPException(
            status_code=404, detail="尚未發布評估結果，請先執行 run_generation_eval --publish"
        )
    return build_report(json.loads(path.read_text(encoding="utf-8")))
