"""Transcript search: semantic and exact text search on transcript embeddings."""
import logging

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings

logger = logging.getLogger(__name__)


def encode_transcript_query(query: str, text_model) -> list[float]:
    """Encode a text query using the transcript embedding model.

    Returns a normalized embedding vector.
    """
    embedding = text_model.encode(
        [query],
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embedding[0].tolist()


def search_transcript_semantic(
    query_embedding: list[float], db: Session, limit: int = 20
):
    """Semantic search on transcript_embeddings using pgvector.

    Returns list of dicts with video_id, segment_text, start_ms, end_ms, score.
    """
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    result = db.execute(
        text("""
            SELECT te.video_id, te.segment_text, te.start_ms, te.end_ms,
                   1 - (te.embedding <=> :query_emb) AS score
            FROM transcript_embeddings te
            ORDER BY te.embedding <=> :query_emb
            LIMIT :lim
        """),
        {"query_emb": embedding_str, "lim": limit},
    )

    rows = []
    for row in result:
        rows.append({
            "video_id": str(row.video_id),
            "segment_text": row.segment_text,
            "start_ms": row.start_ms,
            "end_ms": row.end_ms,
            "score": float(row.score),
        })
    return rows


def search_transcript_exact(query: str, db: Session, limit: int = 20):
    """Exact text search (case-insensitive ILIKE) on transcript segments.

    Returns list of dicts with video_id, segment_text, start_ms, end_ms.
    """
    result = db.execute(
        text("""
            SELECT te.video_id, te.segment_text, te.start_ms, te.end_ms
            FROM transcript_embeddings te
            WHERE te.segment_text ILIKE :pattern
            ORDER BY te.start_ms
            LIMIT :lim
        """),
        {"pattern": f"%{query}%", "lim": limit},
    )

    rows = []
    for row in result:
        rows.append({
            "video_id": str(row.video_id),
            "segment_text": row.segment_text,
            "start_ms": row.start_ms,
            "end_ms": row.end_ms,
        })
    return rows
