"""Visual search: text-to-video and image-to-video using vision model embeddings."""
import logging
from io import BytesIO

import numpy as np
import torch
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings

logger = logging.getLogger(__name__)


def encode_text_query(query: str, vision_model, device) -> list[float]:
    """Encode a text query using the vision model's text encoder.

    Returns a normalized embedding vector.
    """
    import open_clip

    if settings.VISION_MODEL_FAMILY == "open_clip":
        tokenizer = open_clip.get_tokenizer(settings.VISION_MODEL_NAME)
        tokens = tokenizer([query]).to(device)
        with torch.no_grad():
            text_features = vision_model.encode_text(tokens)
            text_features = torch.nn.functional.normalize(text_features, dim=-1)
        return text_features.cpu().float().numpy()[0].tolist()
    else:
        # PE-Core text encoding
        from core.vision_encoder.tokenizer import tokenize

        tokens = tokenize([query]).to(device)
        with torch.no_grad():
            _, text_features, _ = vision_model(None, tokens)
            text_features = torch.nn.functional.normalize(text_features, dim=-1)
        return text_features.cpu().float().numpy()[0].tolist()


def encode_image_query(
    image_bytes: bytes, vision_model, preprocess, device
) -> list[float]:
    """Encode an uploaded image using the vision model.

    Returns a normalized embedding vector.
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    tensor = preprocess(img).unsqueeze(0).to(device)

    with torch.no_grad():
        if settings.VISION_MODEL_FAMILY == "open_clip":
            features = vision_model.encode_image(tensor)
        else:
            features, _, _ = vision_model(tensor, None)
        features = torch.nn.functional.normalize(features, dim=-1)

    return features.cpu().float().numpy()[0].tolist()


def search_visual(query_embedding: list[float], db: Session, limit: int = 20):
    """Run pgvector nearest-neighbor search on frame_embeddings.

    Returns list of dicts with video_id, timestamp_ms, frame_num, score.
    """
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    result = db.execute(
        text("""
            SELECT fe.video_id, fe.timestamp_ms, fe.frame_num,
                   1 - (fe.embedding <=> :query_emb) AS score
            FROM frame_embeddings fe
            ORDER BY fe.embedding <=> :query_emb
            LIMIT :lim
        """),
        {"query_emb": embedding_str, "lim": limit},
    )

    rows = []
    for row in result:
        rows.append({
            "video_id": str(row.video_id),
            "timestamp_ms": row.timestamp_ms,
            "frame_num": row.frame_num,
            "score": float(row.score),
        })
    return rows
