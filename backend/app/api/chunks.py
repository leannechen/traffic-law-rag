from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_chunk_store
from app.pipeline.articles import ChromaChunkStore
from app.schemas.chunk import ChunkDetail

router = APIRouter()


@router.get("/chunks/{chunk_id}")
def get_chunk(
    chunk_id: str, store: Annotated[ChromaChunkStore, Depends(get_chunk_store)]
) -> ChunkDetail:
    """chunk 的欄位加上整條全文 article_text。

    chunk_id 可以是檢索結果的切塊 id（如 K0040012:35-p2），
    也可以是引用事件裡的條 id（如 K0040012:35）。
    """
    chunk = store.get(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="找不到這個條文")
    return chunk
