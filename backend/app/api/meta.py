from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.ingestion.build_index import META_FILE
from app.ingestion.targets import load_targets
from app.schemas.meta import IndexMeta

router = APIRouter()


@router.get("/meta")
def get_meta() -> IndexMeta:
    path = get_settings().index_dir / META_FILE
    if not path.exists():
        raise HTTPException(status_code=503, detail="索引尚未建立，請先執行 build_index")
    meta = IndexMeta.model_validate_json(path.read_text(encoding="utf-8"))
    # 畫面上法規的順序以 targets.yaml 為準（處罰條例在最前面）。索引裡是依檔名（pcode）排的，
    # 在這裡排，現有索引不必重建；不在清單裡的（理論上不會有）排在最後，保持原本相對順序。
    order = {t.pcode: i for i, t in enumerate(load_targets())}
    meta.laws.sort(key=lambda law: order.get(law.pcode, len(order)))
    return meta
