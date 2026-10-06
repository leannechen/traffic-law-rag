from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.ingestion.build_index import META_FILE
from app.schemas.meta import IndexMeta

router = APIRouter()


@router.get("/meta")
def get_meta() -> IndexMeta:
    path = get_settings().index_dir / META_FILE
    if not path.exists():
        raise HTTPException(status_code=503, detail="索引尚未建立，請先執行 build_index")
    return IndexMeta.model_validate_json(path.read_text(encoding="utf-8"))
