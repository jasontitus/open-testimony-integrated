"""AI Search Bridge Service — connects Open Testimony with VideoIndexer AI models."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from config import settings
from models import Base, VideoIndexStatus
from auth import require_auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Global model holders (loaded at startup)
vision_model = None
vision_preprocess = None
text_model = None
caption_model = None
caption_processor = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_vision_model():
    """Load the vision model (OpenCLIP or PE-Core) into memory."""
    global vision_model, vision_preprocess
    import torch

    device = torch.device(settings.DEVICE)
    logger.info(
        f"Loading vision model: {settings.VISION_MODEL_FAMILY} / "
        f"{settings.VISION_MODEL_NAME} on {device}"
    )

    if settings.VISION_MODEL_FAMILY == "open_clip":
        import open_clip

        model, _, preprocess = open_clip.create_model_and_transforms(
            settings.VISION_MODEL_NAME,
            pretrained=settings.VISION_MODEL_PRETRAINED,
            device=device,
        )
        model.eval()
        vision_model = model
        vision_preprocess = preprocess
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
    """Load the caption model (Qwen3-VL) for frame description generation."""
    global caption_model, caption_processor

    if not settings.CAPTION_ENABLED:
        logger.info("Caption model disabled (CAPTION_ENABLED=false)")
        return

    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor

    logger.info(f"Loading caption model: {settings.CAPTION_MODEL_NAME}")
    caption_processor = AutoProcessor.from_pretrained(settings.CAPTION_MODEL_NAME)
    caption_model = Qwen3VLForConditionalGeneration.from_pretrained(
        settings.CAPTION_MODEL_NAME,
        torch_dtype="auto",
        device_map=settings.DEVICE if settings.DEVICE != "cpu" else None,
    )
    if settings.DEVICE == "cpu":
        caption_model = caption_model.float()
    caption_model.eval()
    logger.info("Caption model loaded successfully")


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
        "frame_count": job.frame_count,
        "segment_count": job.segment_count,
        "caption_count": job.caption_count,
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

    # Reset job to pending
    job.status = "pending"
    job.visual_indexed = False
    job.transcript_indexed = False
    job.caption_indexed = False
    job.frame_count = None
    job.segment_count = None
    job.caption_count = None
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
        job.frame_count = None
        job.segment_count = None
        job.caption_count = None
        job.error_message = None
        job.completed_at = None
    db.commit()

    return {"status": "reindex_all_queued", "count": len(jobs)}


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
        "text_model_loaded": text_model is not None,
        "caption_model_loaded": caption_model is not None,
    }
