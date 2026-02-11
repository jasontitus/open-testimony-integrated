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


def _ms(t0, t1):
    """Convert time delta to milliseconds (int)."""
    return int((t1 - t0) * 1000)


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
    return {
        "query": q,
        "mode": "visual_text",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "visual_search_ms": _ms(t_encode, t_search),
            "total_ms": _ms(t0, t_search),
        },
        "results": results,
    }


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
    return {
        "mode": "visual_image",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "visual_search_ms": _ms(t_encode, t_search),
            "total_ms": _ms(t0, t_search),
        },
        "results": results,
    }


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
    return {
        "query": q,
        "mode": "transcript_semantic",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "transcript_search_ms": _ms(t_encode, t_search),
            "total_ms": _ms(t0, t_search),
        },
        "results": results,
    }


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
    return {
        "query": q,
        "mode": "transcript_exact",
        "timing": {
            "search_ms": _ms(t0, t_search),
            "total_ms": _ms(t0, t_search),
        },
        "results": results,
    }


@router.get("/captions")
async def caption_search(
    q: str = Query(..., min_length=1, description="Text query for caption search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Search AI-generated frame captions by semantic similarity."""
    from main import text_model
    from search.caption import encode_caption_query, search_captions

    t0 = time.time()
    query_embedding = encode_caption_query(q, text_model)
    t_encode = time.time()
    results = search_captions(query_embedding, db, limit)
    t_search = time.time()
    logger.info(f"caption q={q!r}: encode={t_encode-t0:.3f}s db={t_search-t_encode:.3f}s total={t_search-t0:.3f}s")
    return {
        "query": q,
        "mode": "caption_semantic",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "caption_search_ms": _ms(t_encode, t_search),
            "total_ms": _ms(t0, t_search),
        },
        "results": results,
    }


@router.get("/combined")
async def combined_search(
    q: str = Query(..., min_length=1, description="Text query for combined visual + caption search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Combined search: query both visual (SigLIP) and caption paths, merge and rank."""
    from main import vision_model, text_model
    from search.visual import encode_text_query, search_visual
    from search.caption import encode_caption_query, search_captions

    t0 = time.time()
    device = torch.device(settings.DEVICE)

    # Encode queries for both paths
    visual_embedding = encode_text_query(q, vision_model, device)
    caption_embedding = encode_caption_query(q, text_model)
    t_encode = time.time()

    # Search both paths
    visual_results = search_visual(visual_embedding, db, limit)
    t_visual = time.time()
    caption_results = search_captions(caption_embedding, db, limit)
    t_caption = time.time()

    # Tag results with source
    for r in visual_results:
        r["source"] = "visual"
    for r in caption_results:
        r["source"] = "caption"

    # Merge and deduplicate by (video_id, frame_num)
    merged = {}
    for r in visual_results:
        key = (r["video_id"], r.get("frame_num"))
        merged[key] = {**r, "visual_score": r["score"], "caption_score": None}

    for r in caption_results:
        key = (r["video_id"], r.get("frame_num"))
        if key in merged:
            existing = merged[key]
            # Keep the higher score as primary, record both
            existing["caption_score"] = r["score"]
            existing["caption_text"] = r.get("caption_text")
            if r["score"] > existing["score"]:
                existing["score"] = r["score"]
                existing["source"] = "caption"
            existing["visual_score"] = existing.get("visual_score", existing["score"])
        else:
            merged[key] = {**r, "visual_score": None, "caption_score": r["score"]}

    # Sort by best score descending, take top N
    results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:limit]

    t_end = time.time()
    logger.info(
        f"combined q={q!r}: encode={t_encode-t0:.3f}s visual={t_visual-t_encode:.3f}s "
        f"caption={t_caption-t_visual:.3f}s total={t_end-t0:.3f}s"
    )
    return {
        "query": q,
        "mode": "combined",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "visual_search_ms": _ms(t_encode, t_visual),
            "caption_search_ms": _ms(t_visual, t_caption),
            "total_ms": _ms(t0, t_end),
        },
        "results": results,
    }
