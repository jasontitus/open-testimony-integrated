"""AI Search Bridge Service — connects Open Testimony with VideoIndexer AI models."""
import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from config import settings
from models import ActionEmbedding, Base, ClipEmbedding, VideoIndexStatus
from auth import require_auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Global model holders (loaded at startup)
vision_model = None
vision_preprocess = None
vision_tokenizer = None  # callable: list[str] -> Tensor of input_ids
vision_processor = None  # HF AutoProcessor (used by hf_siglip, handles images + text)
text_model = None
caption_model = None
caption_processor = None

# Locks to serialize model inference so search and indexing can interleave
vision_lock = threading.Lock()
text_lock = threading.Lock()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_vision_model():
    """Load the vision model (HF SigLIP, OpenCLIP, or PE-Core) into memory."""
    global vision_model, vision_preprocess, vision_tokenizer, vision_processor
    import torch

    device = torch.device(settings.DEVICE)
    device_str = str(device)
    logger.info(
        f"Loading vision model: {settings.VISION_MODEL_FAMILY} / "
        f"{settings.VISION_MODEL_NAME} on {device}"
    )

    if settings.VISION_MODEL_FAMILY == "hf_siglip":
        from transformers import AutoModel, AutoProcessor

        processor = AutoProcessor.from_pretrained(settings.VISION_MODEL_NAME)
        model = AutoModel.from_pretrained(
            settings.VISION_MODEL_NAME, device_map=device_str
        )
        model.eval()
        vision_model = model
        vision_processor = processor
        vision_preprocess = None
        vision_tokenizer = None
    elif settings.VISION_MODEL_FAMILY == "open_clip":
        import open_clip

        model, _, preprocess = open_clip.create_model_and_transforms(
            settings.VISION_MODEL_NAME,
            pretrained=settings.VISION_MODEL_PRETRAINED,
            device=device,
        )
        model.eval()
        vision_model = model
        vision_preprocess = preprocess

        # Cache tokenizer — use underlying HF tokenizer directly to avoid
        # open_clip HFTokenizer.batch_encode_plus incompatibility with transformers 5.x
        oc_tok = open_clip.get_tokenizer(settings.VISION_MODEL_NAME)
        if hasattr(oc_tok, 'tokenizer'):
            hf_tok = oc_tok.tokenizer
            ctx_len = oc_tok.context_length
            def _tokenize(texts):
                return hf_tok(
                    texts, return_tensors="pt",
                    max_length=ctx_len, padding="max_length", truncation=True,
                ).input_ids
            vision_tokenizer = _tokenize
            logger.info(f"Using HF tokenizer directly (context_length={ctx_len})")
        else:
            vision_tokenizer = oc_tok
    else:
        # PE-Core model via official perception_models package
        import core.vision_encoder.pe as pe
        import core.vision_encoder.transforms as pe_transforms

        model = pe.CLIP.from_config(settings.VISION_MODEL_NAME, pretrained=True)
        model = model.to(device)
        if settings.USE_FP16:
            model = model.half()
        model.eval()
        vision_model = model
        vision_preprocess = pe_transforms.get_image_transform(model.image_size)

    logger.info("Vision model loaded successfully")


def load_text_model():
    """Load the transcript embedding model (Qwen3-Embedding-8B)."""
    global text_model
    from sentence_transformers import SentenceTransformer

    logger.info(f"Loading text model: {settings.TRANSCRIPT_MODEL_NAME}")
    text_model = SentenceTransformer(
        settings.TRANSCRIPT_MODEL_NAME, device=settings.DEVICE
    )
    logger.info("Text model loaded successfully")


def load_caption_model():
    """Load the caption model for frame description generation.

    Only loads local Qwen3-VL when CAPTION_PROVIDER=local.
    For Gemini provider, no local model is needed.
    """
    global caption_model, caption_processor

    if not settings.CAPTION_ENABLED:
        logger.info("Caption model disabled (CAPTION_ENABLED=false)")
        return

    if settings.CAPTION_PROVIDER == "gemini":
        logger.info(
            f"Captioning via Gemini API (model={settings.CAPTION_MODEL_NAME}). "
            f"No local caption model to load."
        )
        return

    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor

    logger.info(f"Loading local caption model: {settings.CAPTION_MODEL_NAME}")
    caption_processor = AutoProcessor.from_pretrained(settings.CAPTION_MODEL_NAME)
    caption_model = Qwen3VLForConditionalGeneration.from_pretrained(
        settings.CAPTION_MODEL_NAME,
        torch_dtype="auto",
        device_map=settings.DEVICE if settings.DEVICE != "cpu" else None,
    )
    if settings.DEVICE == "cpu":
        caption_model = caption_model.float()
    caption_model.eval()
    logger.info("Local caption model loaded successfully")


def _migrate_embedding_dimensions():
    """Auto-migrate schema when embedding dimensions change or new tables are needed."""
    with engine.connect() as conn:
        # Check frame_embeddings column dimension
        row = conn.execute(text("""
            SELECT atttypmod FROM pg_attribute
            JOIN pg_class ON pg_class.oid = pg_attribute.attrelid
            WHERE pg_class.relname = 'frame_embeddings'
            AND pg_attribute.attname = 'embedding'
        """)).fetchone()

        if row and row[0] != settings.VISION_EMBEDDING_DIM:
            logger.warning(
                f"frame_embeddings.embedding dimension mismatch: "
                f"DB={row[0]}, config={settings.VISION_EMBEDDING_DIM}. "
                f"Dropping and recreating column (data will be regenerated via reindex)."
            )
            conn.execute(text("ALTER TABLE frame_embeddings DROP COLUMN embedding"))
            conn.execute(text(
                f"ALTER TABLE frame_embeddings ADD COLUMN embedding vector({settings.VISION_EMBEDDING_DIM})"
            ))
            conn.commit()

        # Check clip_embeddings column dimension (also uses VISION_EMBEDDING_DIM)
        clip_row = conn.execute(text("""
            SELECT atttypmod FROM pg_attribute
            JOIN pg_class ON pg_class.oid = pg_attribute.attrelid
            WHERE pg_class.relname = 'clip_embeddings'
            AND pg_attribute.attname = 'embedding'
        """)).fetchone()

        if clip_row and clip_row[0] != settings.VISION_EMBEDDING_DIM:
            logger.warning(
                f"clip_embeddings.embedding dimension mismatch: "
                f"DB={clip_row[0]}, config={settings.VISION_EMBEDDING_DIM}. "
                f"Dropping and recreating column (data will be regenerated via reindex)."
            )
            conn.execute(text("ALTER TABLE clip_embeddings DROP COLUMN embedding"))
            conn.execute(text(
                f"ALTER TABLE clip_embeddings ADD COLUMN embedding vector({settings.VISION_EMBEDDING_DIM})"
            ))
            conn.commit()

        # Add caption_indexed / caption_count to video_index_status if missing
        cols = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'video_index_status'
        """)).fetchall()
        col_names = {c[0] for c in cols}

        if "caption_indexed" not in col_names:
            logger.info("Adding caption_indexed column to video_index_status")
            conn.execute(text(
                "ALTER TABLE video_index_status ADD COLUMN caption_indexed BOOLEAN DEFAULT false"
            ))
        if "caption_count" not in col_names:
            logger.info("Adding caption_count column to video_index_status")
            conn.execute(text(
                "ALTER TABLE video_index_status ADD COLUMN caption_count INTEGER"
            ))
        conn.commit()

        # Create caption_embeddings table if missing
        table_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'caption_embeddings'
            )
        """)).scalar()

        if not table_exists:
            logger.info("Creating caption_embeddings table")
            conn.execute(text(f"""
                CREATE TABLE caption_embeddings (
                    id BIGSERIAL PRIMARY KEY,
                    video_id UUID NOT NULL,
                    frame_num INTEGER NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    caption_text TEXT NOT NULL,
                    embedding vector({settings.TRANSCRIPT_EMBEDDING_DIM}),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_caption_embeddings_video_id "
                "ON caption_embeddings (video_id)"
            ))
            conn.commit()

        # Add clip_indexed / clip_count to video_index_status if missing
        if "clip_indexed" not in col_names:
            logger.info("Adding clip_indexed column to video_index_status")
            conn.execute(text(
                "ALTER TABLE video_index_status ADD COLUMN clip_indexed BOOLEAN DEFAULT false"
            ))
        if "clip_count" not in col_names:
            logger.info("Adding clip_count column to video_index_status")
            conn.execute(text(
                "ALTER TABLE video_index_status ADD COLUMN clip_count INTEGER"
            ))
        conn.commit()

        # Create clip_embeddings table if missing
        clip_table_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'clip_embeddings'
            )
        """)).scalar()

        if not clip_table_exists:
            logger.info("Creating clip_embeddings table")
            conn.execute(text(f"""
                CREATE TABLE clip_embeddings (
                    id BIGSERIAL PRIMARY KEY,
                    video_id UUID NOT NULL,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL,
                    start_frame INTEGER NOT NULL,
                    end_frame INTEGER NOT NULL,
                    num_frames INTEGER NOT NULL,
                    embedding vector({settings.VISION_EMBEDDING_DIM}),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_clip_embeddings_video_id "
                "ON clip_embeddings (video_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS clip_emb_hnsw "
                "ON clip_embeddings USING hnsw (embedding vector_cosine_ops)"
            ))
            conn.commit()

        # Create action_embeddings table if missing
        action_table_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'action_embeddings'
            )
        """)).scalar()

        if not action_table_exists:
            logger.info("Creating action_embeddings table")
            conn.execute(text(f"""
                CREATE TABLE action_embeddings (
                    id BIGSERIAL PRIMARY KEY,
                    video_id UUID NOT NULL,
                    start_ms INTEGER NOT NULL,
                    end_ms INTEGER NOT NULL,
                    start_frame INTEGER NOT NULL,
                    end_frame INTEGER NOT NULL,
                    num_frames INTEGER NOT NULL,
                    action_text TEXT NOT NULL,
                    embedding vector({settings.TRANSCRIPT_EMBEDDING_DIM}),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_action_embeddings_video_id "
                "ON action_embeddings (video_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS action_emb_hnsw "
                "ON action_embeddings USING hnsw (embedding vector_cosine_ops)"
            ))
            conn.commit()

        # Trigram indexes for ILIKE exact-text search on captions, transcripts, and actions
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_caption_text_trgm "
            "ON caption_embeddings USING gin (caption_text gin_trgm_ops)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_transcript_text_trgm "
            "ON transcript_embeddings USING gin (segment_text gin_trgm_ops)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_action_text_trgm "
            "ON action_embeddings USING gin (action_text gin_trgm_ops)"
        ))
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load AI models on startup, start background indexing worker."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    _migrate_embedding_dimensions()
    load_vision_model()
    load_text_model()
    load_caption_model()

    # Start the background indexing worker
    from indexing.worker import indexing_worker

    worker_task = asyncio.create_task(indexing_worker())
    logger.info("Background indexing worker started")

    yield

    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("Bridge service shutting down")


app = FastAPI(
    title="AI Search Bridge",
    description="Connects Open Testimony with VideoIndexer AI-powered search",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Webhook: enqueue video for indexing ---


class VideoUploadedPayload(BaseModel):
    video_id: str
    object_name: str


@app.post("/hooks/video-uploaded")
async def video_uploaded_hook(payload: VideoUploadedPayload, db: Session = Depends(get_db)):
    """Webhook called by OT API after a successful video upload.
    Creates a pending indexing job."""
    import uuid as uuid_mod

    try:
        video_uuid = uuid_mod.UUID(payload.video_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid video_id format")

    existing = (
        db.query(VideoIndexStatus)
        .filter(VideoIndexStatus.video_id == video_uuid)
        .first()
    )
    if existing:
        return {"status": "already_queued", "video_id": payload.video_id}

    job = VideoIndexStatus(
        video_id=video_uuid,
        object_name=payload.object_name,
        status="pending",
    )
    db.add(job)
    db.commit()

    logger.info(f"Queued indexing for video {payload.video_id}")
    return {"status": "queued", "video_id": payload.video_id}


# --- Indexing status endpoints ---


@app.get("/indexing/status")
async def indexing_overview(
    _user: dict = Depends(require_auth), db: Session = Depends(get_db)
):
    """Overall indexing statistics."""
    from sqlalchemy import func

    rows = (
        db.query(VideoIndexStatus.status, func.count())
        .group_by(VideoIndexStatus.status)
        .all()
    )
    counts = {status: count for status, count in rows}
    return {
        "total": sum(counts.values()),
        "pending": counts.get("pending", 0),
        "pending_visual": counts.get("pending_visual", 0),
        "pending_fix": counts.get("pending_fix", 0),
        "processing": counts.get("processing", 0),
        "completed": counts.get("completed", 0),
        "failed": counts.get("failed", 0),
    }


@app.get("/indexing/status/{video_id}")
async def indexing_status_for_video(
    video_id: str,
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Indexing status for a specific video."""
    import uuid as uuid_mod

    job = (
        db.query(VideoIndexStatus)
        .filter(VideoIndexStatus.video_id == uuid_mod.UUID(video_id))
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No indexing job found")
    return {
        "video_id": str(job.video_id),
        "status": job.status,
        "visual_indexed": job.visual_indexed,
        "transcript_indexed": job.transcript_indexed,
        "caption_indexed": job.caption_indexed,
        "clip_indexed": job.clip_indexed,
        "frame_count": job.frame_count,
        "segment_count": job.segment_count,
        "caption_count": job.caption_count,
        "clip_count": job.clip_count,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@app.post("/indexing/reindex/{video_id}")
async def reindex_video(
    video_id: str,
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Manually trigger re-indexing for a video (admin)."""
    import uuid as uuid_mod
    from models import FrameEmbedding, TranscriptEmbedding, CaptionEmbedding

    video_uuid = uuid_mod.UUID(video_id)

    job = (
        db.query(VideoIndexStatus)
        .filter(VideoIndexStatus.video_id == video_uuid)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No indexing job found")

    # Delete existing embeddings
    db.query(FrameEmbedding).filter(FrameEmbedding.video_id == video_uuid).delete()
    db.query(TranscriptEmbedding).filter(
        TranscriptEmbedding.video_id == video_uuid
    ).delete()
    db.query(CaptionEmbedding).filter(
        CaptionEmbedding.video_id == video_uuid
    ).delete()
    db.query(ClipEmbedding).filter(ClipEmbedding.video_id == video_uuid).delete()
    db.query(ActionEmbedding).filter(ActionEmbedding.video_id == video_uuid).delete()

    # Reset job to pending
    job.status = "pending"
    job.visual_indexed = False
    job.transcript_indexed = False
    job.caption_indexed = False
    job.clip_indexed = False
    job.frame_count = None
    job.segment_count = None
    job.caption_count = None
    job.clip_count = None
    job.error_message = None
    job.completed_at = None
    db.commit()

    return {"status": "reindex_queued", "video_id": video_id}


@app.post("/indexing/reindex-all")
async def reindex_all(
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Re-index all videos (admin). Also creates index jobs for any videos missing from the index."""
    from models import FrameEmbedding, TranscriptEmbedding, CaptionEmbedding

    db.query(FrameEmbedding).delete()
    db.query(TranscriptEmbedding).delete()
    db.query(CaptionEmbedding).delete()
    db.query(ClipEmbedding).delete()
    db.query(ActionEmbedding).delete()

    # Create index jobs for any videos in the videos table that have no index status entry
    missing = db.execute(
        text(
            "SELECT id, object_name FROM videos "
            "WHERE id NOT IN (SELECT video_id FROM video_index_status)"
        )
    ).fetchall()
    for row in missing:
        db.add(VideoIndexStatus(
            video_id=row[0],
            object_name=row[1],
            status="pending",
        ))

    # Reset all existing jobs to pending
    jobs = db.query(VideoIndexStatus).all()
    for job in jobs:
        job.status = "pending"
        job.visual_indexed = False
        job.transcript_indexed = False
        job.caption_indexed = False
        job.clip_indexed = False
        job.frame_count = None
        job.segment_count = None
        job.caption_count = None
        job.clip_count = None
        job.error_message = None
        job.completed_at = None
    db.commit()

    return {"status": "reindex_all_queued", "count": len(jobs)}


@app.post("/indexing/reindex-visual/{video_id}")
async def reindex_visual_video(
    video_id: str,
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Re-encode visual embeddings only for a single video (admin).

    Preserves existing caption and transcript embeddings.
    Use after switching vision models to avoid re-running Gemini/Whisper.
    Only acts on completed or failed videos — refuses if still pending/processing.
    """
    import uuid as uuid_mod
    from models import FrameEmbedding

    video_uuid = uuid_mod.UUID(video_id)

    job = (
        db.query(VideoIndexStatus)
        .filter(VideoIndexStatus.video_id == video_uuid)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No indexing job found")

    if job.status in ("pending", "processing"):
        raise HTTPException(
            status_code=409,
            detail=f"Video is currently '{job.status}' — wait for full indexing "
                   f"to finish before visual reindex",
        )

    # Clear visual state + clips/actions (all depend on the vision model),
    # leave captions/transcripts intact
    db.query(FrameEmbedding).filter(FrameEmbedding.video_id == video_uuid).delete()
    db.query(ClipEmbedding).filter(ClipEmbedding.video_id == video_uuid).delete()
    db.query(ActionEmbedding).filter(ActionEmbedding.video_id == video_uuid).delete()
    job.status = "pending_visual"
    job.visual_indexed = False
    job.frame_count = None
    job.clip_indexed = False
    job.clip_count = None
    job.error_message = None
    db.commit()

    return {"status": "visual_reindex_queued", "video_id": video_id}


@app.post("/indexing/reindex-visual-all")
async def reindex_visual_all(
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Re-encode visual embeddings for all completed/failed videos (admin).

    Preserves existing caption and transcript embeddings.
    Use after switching vision models to avoid re-running Gemini/Whisper.
    Skips videos that are still pending or processing full indexing.
    """
    from models import FrameEmbedding

    jobs = db.query(VideoIndexStatus).all()
    queued = []
    skipped = []

    for job in jobs:
        if job.status in ("pending", "processing"):
            skipped.append(str(job.video_id))
            continue

        # Delete visual embeddings (frames + clips + actions) for this video
        db.query(FrameEmbedding).filter(
            FrameEmbedding.video_id == job.video_id
        ).delete()
        db.query(ClipEmbedding).filter(
            ClipEmbedding.video_id == job.video_id
        ).delete()
        db.query(ActionEmbedding).filter(
            ActionEmbedding.video_id == job.video_id
        ).delete()
        job.status = "pending_visual"
        job.visual_indexed = False
        job.frame_count = None
        job.clip_indexed = False
        job.clip_count = None
        job.error_message = None
        queued.append(str(job.video_id))

    db.commit()

    result = {"status": "visual_reindex_all_queued", "queued": len(queued)}
    if skipped:
        result["skipped"] = len(skipped)
        result["skipped_reason"] = "still pending/processing full indexing"
        result["skipped_video_ids"] = skipped
    return result


@app.post("/indexing/fix/{video_id}")
async def fix_video(
    video_id: str,
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Fix missing indexes for a single video (admin).

    Checks which embedding tables have data and only generates what's missing.
    Does not delete any existing embeddings.
    """
    import uuid as uuid_mod

    video_uuid = uuid_mod.UUID(video_id)

    job = (
        db.query(VideoIndexStatus)
        .filter(VideoIndexStatus.video_id == video_uuid)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No indexing job found")

    if job.status in ("pending", "processing"):
        raise HTTPException(
            status_code=409,
            detail=f"Video is currently '{job.status}' — wait for it to finish",
        )

    job.status = "pending_fix"
    job.error_message = None
    db.commit()

    return {"status": "fix_queued", "video_id": video_id}


@app.post("/indexing/fix-all")
async def fix_all(
    _user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Fix missing indexes for all videos (admin).

    Checks each video's embedding tables and only generates what's missing.
    Skips videos that are still pending or processing.
    Does not delete any existing embeddings.
    """
    jobs = db.query(VideoIndexStatus).all()
    queued = []
    skipped = []

    for job in jobs:
        if job.status in ("pending", "processing"):
            skipped.append(str(job.video_id))
            continue
        job.status = "pending_fix"
        job.error_message = None
        queued.append(str(job.video_id))

    db.commit()

    result = {"status": "fix_all_queued", "queued": len(queued)}
    if skipped:
        result["skipped"] = len(skipped)
        result["skipped_reason"] = "still pending/processing"
        result["skipped_video_ids"] = skipped
    return result


# --- Thumbnail serving ---


@app.get("/thumbnails/{video_id}/{timestamp_ms}.jpg")
async def get_thumbnail(video_id: str, timestamp_ms: int):
    """Serve a thumbnail image for a video frame.
    Falls back to nearest available thumbnail if exact match not found."""
    import os
    import glob

    thumb_dir = os.path.join(settings.THUMBNAIL_DIR, video_id)
    exact = os.path.join(thumb_dir, f"{timestamp_ms}.jpg")
    if os.path.exists(exact):
        return FileResponse(exact, media_type="image/jpeg")

    # Fallback: find nearest available thumbnail
    if os.path.isdir(thumb_dir):
        available = glob.glob(os.path.join(thumb_dir, "*.jpg"))
        if available:
            def ts_from_path(p):
                return int(os.path.basename(p).replace(".jpg", ""))
            nearest = min(available, key=lambda p: abs(ts_from_path(p) - timestamp_ms))
            return FileResponse(nearest, media_type="image/jpeg")

    raise HTTPException(status_code=404, detail="Thumbnail not found")


# --- Search endpoints (from search router) ---

from search.router import router as search_router

app.include_router(search_router)


# --- Health check ---


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "vision_model_loaded": vision_model is not None,
        "vision_model_family": settings.VISION_MODEL_FAMILY,
        "text_model_loaded": text_model is not None,
        "caption_model_loaded": caption_model is not None,
        "caption_provider": settings.CAPTION_PROVIDER,
        "caption_model_name": settings.CAPTION_MODEL_NAME,
        "clip_enabled": settings.CLIP_ENABLED,
        "clip_window_frames": settings.CLIP_WINDOW_FRAMES,
        "clip_window_stride": settings.CLIP_WINDOW_STRIDE,
        "clip_fps": settings.CLIP_FPS,
    }
