"""Clip search: temporal video clip search for motion/action understanding.

Two search paths:
  - clip_visual: Text query encoded with vision model, searched against mean-pooled
    clip embeddings (captures what the window LOOKS like across time)
  - clip_action: Text query encoded with text model, searched against action caption
    embeddings (captures described ACTIONS happening across time)
"""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings

logger = logging.getLogger(__name__)


def encode_action_query(query: str, text_model) -> list[float]:
    """Encode a text query using the text embedding model for action search.

    Returns a normalized embedding vector.
    """
    embedding = text_model.encode(
        [query],
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embedding[0].tolist()


def search_clips_visual(query_embedding: list[float], db: Session, limit: int = 20):
    """Search clip_embeddings (mean-pooled vision embeddings) by visual similarity.

    Returns list of dicts with video_id, start_ms, end_ms, num_frames, score.
    """
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    result = db.execute(
        text("""
            SELECT ce.video_id, ce.start_ms, ce.end_ms,
                   ce.start_frame, ce.end_frame, ce.num_frames,
                   1 - (ce.embedding <=> :query_emb) AS score
            FROM clip_embeddings ce
            ORDER BY ce.embedding <=> :query_emb
            LIMIT :lim
        """),
        {"query_emb": embedding_str, "lim": limit},
    )

    rows = []
    for row in result:
        vid = str(row.video_id)
        # Use the midpoint timestamp for the thumbnail
        mid_ms = (row.start_ms + row.end_ms) // 2
        rows.append({
            "video_id": vid,
            "start_ms": row.start_ms,
            "end_ms": row.end_ms,
            "start_frame": row.start_frame,
            "end_frame": row.end_frame,
            "num_frames": row.num_frames,
            "duration_ms": row.end_ms - row.start_ms,
            "score": float(row.score),
            "thumbnail_url": f"/thumbnails/{vid}/{mid_ms}.jpg",
        })
    return rows


def search_actions_semantic(query_embedding: list[float], db: Session, limit: int = 20):
    """Search action_embeddings (temporal action captions) by semantic similarity.

    Returns list of dicts with video_id, start_ms, end_ms, action_text, score.
    """
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    result = db.execute(
        text("""
            SELECT ae.video_id, ae.start_ms, ae.end_ms,
                   ae.start_frame, ae.end_frame, ae.num_frames,
                   ae.action_text,
                   1 - (ae.embedding <=> :query_emb) AS score
            FROM action_embeddings ae
            ORDER BY ae.embedding <=> :query_emb
            LIMIT :lim
        """),
        {"query_emb": embedding_str, "lim": limit},
    )

    rows = []
    for row in result:
        vid = str(row.video_id)
        mid_ms = (row.start_ms + row.end_ms) // 2
        rows.append({
            "video_id": vid,
            "start_ms": row.start_ms,
            "end_ms": row.end_ms,
            "start_frame": row.start_frame,
            "end_frame": row.end_frame,
            "num_frames": row.num_frames,
            "duration_ms": row.end_ms - row.start_ms,
            "action_text": row.action_text,
            "score": float(row.score),
            "thumbnail_url": f"/thumbnails/{vid}/{mid_ms}.jpg",
        })
    return rows


def search_actions_exact(query: str, db: Session, limit: int = 20):
    """Exact text search (case-insensitive ILIKE) on action captions.

    Returns list of dicts with video_id, start_ms, end_ms, action_text.
    """
    result = db.execute(
        text("""
            SELECT ae.video_id, ae.start_ms, ae.end_ms,
                   ae.start_frame, ae.end_frame, ae.num_frames,
                   ae.action_text
            FROM action_embeddings ae
            WHERE ae.action_text ILIKE :pattern
            ORDER BY ae.start_ms
            LIMIT :lim
        """),
        {"pattern": f"%{query}%", "lim": limit},
    )

    rows = []
    for row in result:
        vid = str(row.video_id)
        mid_ms = (row.start_ms + row.end_ms) // 2
        rows.append({
            "video_id": vid,
            "start_ms": row.start_ms,
            "end_ms": row.end_ms,
            "start_frame": row.start_frame,
            "end_frame": row.end_frame,
            "num_frames": row.num_frames,
            "duration_ms": row.end_ms - row.start_ms,
            "action_text": row.action_text,
            "thumbnail_url": f"/thumbnails/{vid}/{mid_ms}.jpg",
        })
    return rows
