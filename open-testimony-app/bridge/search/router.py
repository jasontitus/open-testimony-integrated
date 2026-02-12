"""FastAPI router for search endpoints."""
import asyncio
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


def _visual_text_encode_and_search(q, db, limit):
    """Run visual text encoding + DB search under the vision lock."""
    from main import vision_model, vision_lock
    from search.visual import encode_text_query, search_visual

    device = torch.device(settings.DEVICE)
    with vision_lock:
        query_embedding = encode_text_query(q, vision_model, device)
    t_encode = time.time()
    results = search_visual(query_embedding, db, limit)
    t_search = time.time()
    return query_embedding, results, t_encode, t_search


@router.get("/visual")
async def visual_text_search(
    q: str = Query(..., min_length=1, description="Text query for visual search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Text-to-video visual search: encode query text with vision model, find similar frames."""
    t0 = time.time()
    _, results, t_encode, t_search = await asyncio.to_thread(
        _visual_text_encode_and_search, q, db, limit
    )
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


def _visual_image_encode_and_search(image_bytes, db, limit):
    """Run visual image encoding + DB search under the vision lock."""
    from main import vision_model, vision_preprocess, vision_lock
    from search.visual import encode_image_query, search_visual

    device = torch.device(settings.DEVICE)
    with vision_lock:
        query_embedding = encode_image_query(
            image_bytes, vision_model, vision_preprocess, device
        )
    t_encode = time.time()
    results = search_visual(query_embedding, db, limit)
    t_search = time.time()
    return results, t_encode, t_search


@router.post("/visual")
async def visual_image_search(
    image: UploadFile = File(...),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Image-to-video visual search: encode uploaded image, find similar frames."""
    t0 = time.time()
    image_bytes = await image.read()
    results, t_encode, t_search = await asyncio.to_thread(
        _visual_image_encode_and_search, image_bytes, db, limit
    )
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


def _transcript_encode_and_search(q, db, limit):
    """Run transcript encoding + DB search under the text lock."""
    from main import text_model, text_lock
    from search.transcript import encode_transcript_query, search_transcript_semantic

    with text_lock:
        query_embedding = encode_transcript_query(q, text_model)
    t_encode = time.time()
    results = search_transcript_semantic(query_embedding, db, limit)
    t_search = time.time()
    return results, t_encode, t_search


@router.get("/transcript")
async def transcript_semantic_search(
    q: str = Query(..., min_length=1, description="Text query for semantic transcript search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Semantic transcript search: encode query with text model, find similar segments."""
    t0 = time.time()
    results, t_encode, t_search = await asyncio.to_thread(
        _transcript_encode_and_search, q, db, limit
    )
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


def _transcript_exact_search(q, db, limit):
    """Run exact transcript search (no model, just DB)."""
    from search.transcript import search_transcript_exact

    results = search_transcript_exact(q, db, limit)
    t_search = time.time()
    return results, t_search


@router.get("/transcript/exact")
async def transcript_exact_search(
    q: str = Query(..., min_length=1, description="Text query for exact transcript search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Exact text search on transcript segments (case-insensitive)."""
    t0 = time.time()
    results, t_search = await asyncio.to_thread(
        _transcript_exact_search, q, db, limit
    )
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


def _caption_encode_and_search(q, db, limit):
    """Run caption encoding + DB search under the text lock."""
    from main import text_model, text_lock
    from search.caption import encode_caption_query, search_captions

    with text_lock:
        query_embedding = encode_caption_query(q, text_model)
    t_encode = time.time()
    results = search_captions(query_embedding, db, limit)
    t_search = time.time()
    return results, t_encode, t_search


@router.get("/captions")
async def caption_search(
    q: str = Query(..., min_length=1, description="Text query for caption search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Search AI-generated frame captions by semantic similarity."""
    t0 = time.time()
    results, t_encode, t_search = await asyncio.to_thread(
        _caption_encode_and_search, q, db, limit
    )
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


def _combined_encode_and_search(q, db, limit):
    """Run combined visual+caption encoding and search under locks."""
    from main import vision_model, text_model, vision_lock, text_lock
    from search.visual import encode_text_query, search_visual
    from search.caption import encode_caption_query, search_captions

    device = torch.device(settings.DEVICE)

    # Encode queries — acquire each lock only for the model call
    with vision_lock:
        visual_embedding = encode_text_query(q, vision_model, device)
    with text_lock:
        caption_embedding = encode_caption_query(q, text_model)
    t_encode = time.time()

    # DB searches (no model lock needed)
    visual_results = search_visual(visual_embedding, db, limit)
    t_visual = time.time()
    caption_results = search_captions(caption_embedding, db, limit)
    t_caption = time.time()

    return visual_results, caption_results, t_encode, t_visual, t_caption


@router.get("/combined")
async def combined_search(
    q: str = Query(..., min_length=1, description="Text query for combined visual + caption search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Combined search: query both visual (SigLIP) and caption paths, merge and rank."""
    t0 = time.time()

    visual_results, caption_results, t_encode, t_visual, t_caption = (
        await asyncio.to_thread(_combined_encode_and_search, q, db, limit)
    )

    # Tag results with source and assign RRF rank scores.
    # Raw scores from SigLIP (~0.1-0.3) and Qwen3-Embedding (~0.4-0.6) are on
    # different scales, so we use Reciprocal Rank Fusion (k=60) to combine them
    # fairly based on rank position rather than raw similarity.
    RRF_K = 60
    for rank, r in enumerate(visual_results):
        r["source"] = "visual"
        r["rrf_score"] = 1.0 / (RRF_K + rank + 1)
    for rank, r in enumerate(caption_results):
        r["source"] = "caption"
        r["rrf_score"] = 1.0 / (RRF_K + rank + 1)

    # Merge and deduplicate by (video_id, frame_num)
    merged = {}
    for r in visual_results:
        key = (r["video_id"], r.get("frame_num"))
        merged[key] = {**r, "visual_score": r["score"], "caption_score": None}

    for r in caption_results:
        key = (r["video_id"], r.get("frame_num"))
        if key in merged:
            existing = merged[key]
            # Same frame in both indexes — sum RRF scores, keep both raw scores
            existing["rrf_score"] += r["rrf_score"]
            existing["caption_score"] = r["score"]
            existing["caption_text"] = r.get("caption_text")
            existing["source"] = "both"
        else:
            merged[key] = {**r, "visual_score": None, "caption_score": r["score"]}

    # Sort by RRF score descending, take top N
    results = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)[:limit]

    # Set display score to RRF score (normalized to 0-1 range for UI)
    max_rrf = results[0]["rrf_score"] if results else 1.0
    for r in results:
        r["score"] = r["rrf_score"] / max_rrf  # normalize so best = 1.0

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
