"""FastAPI router for search endpoints."""
import asyncio
import logging
import time

import torch
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from auth import require_auth
from config import settings
from models import SearchQuery

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


def _log_search(db: Session, query_text: str, search_mode: str,
                result_count: int, duration_ms: int):
    """Record a search query to the database for analytics (no PII)."""
    try:
        entry = SearchQuery(
            query_text=query_text,
            search_mode=search_mode,
            result_count=result_count,
            duration_ms=duration_ms,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to log search query", exc_info=True)


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
    total_ms = _ms(t0, t_search)
    logger.info(f"visual_text q={q!r}: encode={t_encode-t0:.3f}s db={t_search-t_encode:.3f}s total={t_search-t0:.3f}s")
    _log_search(db, q, "visual", len(results), total_ms)
    return {
        "query": q,
        "mode": "visual_text",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "visual_search_ms": _ms(t_encode, t_search),
            "total_ms": total_ms,
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
    total_ms = _ms(t0, t_search)
    logger.info(f"transcript_semantic q={q!r}: encode={t_encode-t0:.3f}s db={t_search-t_encode:.3f}s total={t_search-t0:.3f}s")
    _log_search(db, q, "transcript", len(results), total_ms)
    return {
        "query": q,
        "mode": "transcript_semantic",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "transcript_search_ms": _ms(t_encode, t_search),
            "total_ms": total_ms,
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
    total_ms = _ms(t0, t_search)
    logger.info(f"transcript_exact q={q!r}: db={t_search-t0:.3f}s")
    _log_search(db, q, "transcript_exact", len(results), total_ms)
    return {
        "query": q,
        "mode": "transcript_exact",
        "timing": {
            "search_ms": total_ms,
            "total_ms": total_ms,
        },
        "results": results,
    }


def _caption_exact_search(q, db, limit):
    """Run exact caption search (no model, just DB)."""
    from search.caption import search_captions_exact

    results = search_captions_exact(q, db, limit)
    t_search = time.time()
    return results, t_search


@router.get("/captions/exact")
async def caption_exact_search(

    q: str = Query(..., min_length=1, description="Text query for exact caption search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Exact text search on AI-generated captions (case-insensitive)."""
    t0 = time.time()
    results, t_search = await asyncio.to_thread(
        _caption_exact_search, q, db, limit
    )
    total_ms = _ms(t0, t_search)
    logger.info(f"caption_exact q={q!r}: db={t_search-t0:.3f}s")
    _log_search(db, q, "caption_exact", len(results), total_ms)
    return {
        "query": q,
        "mode": "caption_exact",
        "timing": {
            "search_ms": total_ms,
            "total_ms": total_ms,
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
    total_ms = _ms(t0, t_search)
    logger.info(f"caption q={q!r}: encode={t_encode-t0:.3f}s db={t_search-t_encode:.3f}s total={t_search-t0:.3f}s")
    _log_search(db, q, "caption", len(results), total_ms)
    return {
        "query": q,
        "mode": "caption_semantic",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "caption_search_ms": _ms(t_encode, t_search),
            "total_ms": total_ms,
        },
        "results": results,
    }


def _clip_visual_encode_and_search(q, db, limit):
    """Run clip visual text encoding + DB search under the vision lock."""
    from main import vision_model, vision_lock
    from search.visual import encode_text_query
    from search.clip import search_clips_visual

    device = torch.device(settings.DEVICE)
    with vision_lock:
        query_embedding = encode_text_query(q, vision_model, device)
    t_encode = time.time()
    results = search_clips_visual(query_embedding, db, limit)
    t_search = time.time()
    return results, t_encode, t_search


@router.get("/clips")
async def clip_visual_search(

    q: str = Query(..., min_length=1, description="Text query for clip-level visual search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Clip-level visual search: encode query with vision model, find similar temporal windows.

    Uses mean-pooled frame embeddings across overlapping clip windows to capture
    motion and temporal content that single-frame search misses.
    """
    t0 = time.time()
    results, t_encode, t_search = await asyncio.to_thread(
        _clip_visual_encode_and_search, q, db, limit
    )
    total_ms = _ms(t0, t_search)
    logger.info(f"clip_visual q={q!r}: encode={t_encode-t0:.3f}s db={t_search-t_encode:.3f}s total={t_search-t0:.3f}s")
    _log_search(db, q, "clips", len(results), total_ms)
    return {
        "query": q,
        "mode": "clip_visual",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "clip_search_ms": _ms(t_encode, t_search),
            "total_ms": total_ms,
        },
        "results": results,
    }


def _action_encode_and_search(q, db, limit):
    """Run action text encoding + DB search under the text lock."""
    from main import text_model, text_lock
    from search.clip import encode_action_query, search_actions_semantic

    with text_lock:
        query_embedding = encode_action_query(q, text_model)
    t_encode = time.time()
    results = search_actions_semantic(query_embedding, db, limit)
    t_search = time.time()
    return results, t_encode, t_search


@router.get("/actions")
async def action_search(

    q: str = Query(..., min_length=1, description="Text query for action/motion search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Search for actions and physical interactions across video clips.

    Searches temporal action captions generated from overlapping frame windows.
    Use queries like 'chokehold', 'pushing', 'use of force', 'person being restrained'.
    """
    t0 = time.time()
    results, t_encode, t_search = await asyncio.to_thread(
        _action_encode_and_search, q, db, limit
    )
    total_ms = _ms(t0, t_search)
    logger.info(f"action q={q!r}: encode={t_encode-t0:.3f}s db={t_search-t_encode:.3f}s total={t_search-t0:.3f}s")
    _log_search(db, q, "actions", len(results), total_ms)
    return {
        "query": q,
        "mode": "action_semantic",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "action_search_ms": _ms(t_encode, t_search),
            "total_ms": total_ms,
        },
        "results": results,
    }


def _action_exact_search(q, db, limit):
    """Run exact action caption search (no model, just DB)."""
    from search.clip import search_actions_exact

    results = search_actions_exact(q, db, limit)
    t_search = time.time()
    return results, t_search


@router.get("/actions/exact")
async def action_exact_search(

    q: str = Query(..., min_length=1, description="Text query for exact action search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Exact text search on temporal action captions (case-insensitive)."""
    t0 = time.time()
    results, t_search = await asyncio.to_thread(
        _action_exact_search, q, db, limit
    )
    total_ms = _ms(t0, t_search)
    logger.info(f"action_exact q={q!r}: db={t_search-t0:.3f}s")
    _log_search(db, q, "actions_exact", len(results), total_ms)
    return {
        "query": q,
        "mode": "action_exact",
        "timing": {
            "search_ms": total_ms,
            "total_ms": total_ms,
        },
        "results": results,
    }


def _combined_encode_and_search(q, db, limit):
    """Run combined visual+caption+action encoding and search under locks."""
    from main import vision_model, text_model, vision_lock, text_lock
    from search.visual import encode_text_query, search_visual
    from search.caption import encode_caption_query, search_captions
    from search.clip import search_clips_visual, search_actions_semantic

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

    # Clip-level searches (use same embeddings — vision for clips, text for actions)
    clip_results = []
    action_results = []
    if settings.CLIP_ENABLED:
        clip_results = search_clips_visual(visual_embedding, db, limit)
        action_results = search_actions_semantic(caption_embedding, db, limit)
    t_clips = time.time()

    return visual_results, caption_results, clip_results, action_results, t_encode, t_visual, t_caption, t_clips


@router.get("/combined")
async def combined_search(

    q: str = Query(..., min_length=1, description="Text query for combined visual + caption search"),
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Combined search: query visual, caption, clip, and action paths, merge and rank."""
    t0 = time.time()

    (visual_results, caption_results, clip_results, action_results,
     t_encode, t_visual, t_caption, t_clips) = (
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
    for rank, r in enumerate(clip_results):
        r["source"] = "clip"
        r["rrf_score"] = 1.0 / (RRF_K + rank + 1)
    for rank, r in enumerate(action_results):
        r["source"] = "action"
        r["rrf_score"] = 1.0 / (RRF_K + rank + 1)

    # Merge frame-level results by (video_id, frame_num)
    merged = {}
    for r in visual_results:
        key = (r["video_id"], r.get("frame_num"))
        merged[key] = {**r, "visual_score": r["score"], "caption_score": None}

    for r in caption_results:
        key = (r["video_id"], r.get("frame_num"))
        if key in merged:
            existing = merged[key]
            existing["rrf_score"] += r["rrf_score"]
            existing["caption_score"] = r["score"]
            existing["caption_text"] = r.get("caption_text")
            existing["source"] = "both"
        else:
            merged[key] = {**r, "visual_score": None, "caption_score": r["score"]}

    # Merge clip-level results by (video_id, start_ms) — these are temporal ranges
    for r in clip_results:
        key = (r["video_id"], f"clip_{r['start_ms']}")
        if key not in merged:
            merged[key] = {**r, "visual_score": r["score"], "caption_score": None}
        else:
            merged[key]["rrf_score"] += r["rrf_score"]

    for r in action_results:
        key = (r["video_id"], f"clip_{r['start_ms']}")
        if key in merged:
            existing = merged[key]
            existing["rrf_score"] += r["rrf_score"]
            existing["action_text"] = r.get("action_text")
            if existing["source"] == "clip":
                existing["source"] = "clip+action"
        else:
            merged[key] = {**r, "visual_score": None, "caption_score": None}

    # Sort by RRF score descending, take top N
    results = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)[:limit]

    # Set display score to RRF score (normalized to 0-1 range for UI)
    max_rrf = results[0]["rrf_score"] if results else 1.0
    for r in results:
        r["score"] = r["rrf_score"] / max_rrf  # normalize so best = 1.0

    t_end = time.time()
    total_ms = _ms(t0, t_end)
    logger.info(
        f"combined q={q!r}: encode={t_encode-t0:.3f}s visual={t_visual-t_encode:.3f}s "
        f"caption={t_caption-t_visual:.3f}s clips={t_clips-t_caption:.3f}s total={t_end-t0:.3f}s"
    )
    _log_search(db, q, "combined", len(results), total_ms)
    return {
        "query": q,
        "mode": "combined",
        "timing": {
            "encode_ms": _ms(t0, t_encode),
            "visual_search_ms": _ms(t_encode, t_visual),
            "caption_search_ms": _ms(t_visual, t_caption),
            "clip_search_ms": _ms(t_caption, t_clips),
            "total_ms": total_ms,
        },
        "results": results,
    }
