"""Caption search: semantic search on AI-generated frame descriptions."""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings

logger = logging.getLogger(__name__)


def encode_caption_query(query: str, text_model) -> list[float]:
    """Encode a text query using the text embedding model (same as transcript).

    Returns a normalized embedding vector.
    """
    embedding = text_model.encode(
        [query],
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embedding[0].tolist()


def search_captions(query_embedding: list[float], db: Session, limit: int = 20):
    """Run pgvector nearest-neighbor search on caption_embeddings.

    Returns list of dicts with video_id, timestamp_ms, frame_num, caption_text, score.
    """
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    result = db.execute(
        text("""
            SELECT ce.video_id, ce.timestamp_ms, ce.frame_num, ce.caption_text,
                   1 - (ce.embedding <=> :query_emb) AS score
            FROM caption_embeddings ce
            ORDER BY ce.embedding <=> :query_emb
            LIMIT :lim
        """),
        {"query_emb": embedding_str, "lim": limit},
    )

    rows = []
    for row in result:
        vid = str(row.video_id)
        rows.append({
            "video_id": vid,
            "timestamp_ms": row.timestamp_ms,
            "frame_num": row.frame_num,
            "caption_text": row.caption_text,
            "score": float(row.score),
            "thumbnail_url": f"/thumbnails/{vid}/{row.timestamp_ms}.jpg",
        })
    return rows
