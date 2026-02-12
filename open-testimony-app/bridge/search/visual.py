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
    if settings.VISION_MODEL_FAMILY == "hf_siglip":
        from main import vision_processor

        inputs = vision_processor(
            text=[query], return_tensors="pt",
            padding="max_length", max_length=64,
        ).to(device)
        with torch.no_grad():
            text_features = vision_model.get_text_features(**inputs)
            text_features = torch.nn.functional.normalize(text_features, dim=-1)
        return text_features.cpu().float().numpy()[0].tolist()
    elif settings.VISION_MODEL_FAMILY == "open_clip":
        from main import vision_tokenizer

        tokens = vision_tokenizer([query]).to(device)
        with torch.no_grad():
            text_features = vision_model.encode_text(tokens)
            text_features = torch.nn.functional.normalize(text_features, dim=-1)
        return text_features.cpu().float().numpy()[0].tolist()
    else:
        # PE-Core text encoding
        import core.vision_encoder.transforms as pe_transforms

        tokenizer = pe_transforms.get_text_tokenizer(vision_model.context_length)
        tokens = tokenizer([query]).to(device)
        with torch.no_grad():
            text_features = vision_model.encode_text(tokens)
            text_features = torch.nn.functional.normalize(text_features, dim=-1)
        return text_features.cpu().float().numpy()[0].tolist()


def encode_image_query(
    image_bytes: bytes, vision_model, preprocess, device
) -> list[float]:
    """Encode an uploaded image using the vision model.

    Returns a normalized embedding vector.
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGB")

    if settings.VISION_MODEL_FAMILY == "hf_siglip":
        from main import vision_processor

        inputs = vision_processor(images=img, return_tensors="pt").to(device)
        with torch.no_grad():
            features = vision_model.get_image_features(**inputs)
            features = torch.nn.functional.normalize(features, dim=-1)
        return features.cpu().float().numpy()[0].tolist()

    tensor = preprocess(img).unsqueeze(0).to(device)

    with torch.no_grad():
        features = vision_model.encode_image(tensor)
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
        vid = str(row.video_id)
        rows.append({
            "video_id": vid,
            "timestamp_ms": row.timestamp_ms,
            "frame_num": row.frame_num,
            "score": float(row.score),
            "thumbnail_url": f"/thumbnails/{vid}/{row.timestamp_ms}.jpg",
        })
    return rows
