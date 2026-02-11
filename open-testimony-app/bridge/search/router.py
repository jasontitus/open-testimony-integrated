"""FastAPI router for search endpoints."""
import logging
import time

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

    t0 = time.time()
    device = torch.device(settings.DEVICE)
    query_embedding = encode_text_query(q, vision_model, device)
    t_encode = time.time()
    results = search_visual(query_embedding, db, limit)
    t_search = time.time()
    logger.info(f"visual_text q={q!r}: encode={t_encode-t0:.3f}s db={t_search-t_encode:.3f}s total={t_search-t0:.3f}s")
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

    t0 = time.time()
    device = torch.device(settings.DEVICE)
    image_bytes = await image.read()
    query_embedding = encode_image_query(
        image_bytes, vision_model, vision_preprocess, device
    )
    t_encode = time.time()
    results = search_visual(query_embedding, db, limit)
    t_search = time.time()
    logger.info(f"visual_image: encode={t_encode-t0:.3f}s db={t_search-t_encode:.3f}s total={t_search-t0:.3f}s")
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

    t0 = time.time()
    query_embedding = encode_transcript_query(q, text_model)
    t_encode = time.time()
    results = search_transcript_semantic(query_embedding, db, limit)
    t_search = time.time()
    logger.info(f"transcript_semantic q={q!r}: encode={t_encode-t0:.3f}s db={t_search-t_encode:.3f}s total={t_search-t0:.3f}s")
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

    t0 = time.time()
    results = search_transcript_exact(q, db, limit)
    t_search = time.time()
    logger.info(f"transcript_exact q={q!r}: db={t_search-t0:.3f}s")
    return {"query": q, "mode": "transcript_exact", "results": results}
