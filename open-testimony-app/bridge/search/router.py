"""FastAPI router for search endpoints."""
import logging

import torch
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from auth import require_auth
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


def get_db():
    from main import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/visual")
async def visual_text_search(
    q: str = Query(..., min_length=1, description="Text query for visual search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Text-to-video visual search: encode query text with vision model, find similar frames."""
    from main import vision_model
    from search.visual import encode_text_query, search_visual

    device = torch.device(settings.DEVICE)
    query_embedding = encode_text_query(q, vision_model, device)
    results = search_visual(query_embedding, db, limit)
    return {"query": q, "mode": "visual_text", "results": results}


@router.post("/visual")
async def visual_image_search(
    image: UploadFile = File(...),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Image-to-video visual search: encode uploaded image, find similar frames."""
    from main import vision_model, vision_preprocess
    from search.visual import encode_image_query, search_visual

    device = torch.device(settings.DEVICE)
    image_bytes = await image.read()
    query_embedding = encode_image_query(
        image_bytes, vision_model, vision_preprocess, device
    )
    results = search_visual(query_embedding, db, limit)
    return {"mode": "visual_image", "results": results}


@router.get("/transcript")
async def transcript_semantic_search(
    q: str = Query(..., min_length=1, description="Text query for semantic transcript search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Semantic transcript search: encode query with text model, find similar segments."""
    from main import text_model
    from search.transcript import encode_transcript_query, search_transcript_semantic

    query_embedding = encode_transcript_query(q, text_model)
    results = search_transcript_semantic(query_embedding, db, limit)
    return {"query": q, "mode": "transcript_semantic", "results": results}


@router.get("/transcript/exact")
async def transcript_exact_search(
    q: str = Query(..., min_length=1, description="Text query for exact transcript search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Exact text search on transcript segments (case-insensitive)."""
    from search.transcript import search_transcript_exact

    results = search_transcript_exact(q, db, limit)
    return {"query": q, "mode": "transcript_exact", "results": results}
