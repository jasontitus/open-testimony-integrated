"""Indexing pipeline: extracts frames & transcripts, generates embeddings, stores in pgvector."""
import logging
import os
import tempfile
from datetime import datetime

import cv2
import numpy as np
import torch
from PIL import Image, ImageStat
from sqlalchemy.orm import Session

from config import settings
from models import CaptionEmbedding, FrameEmbedding, TranscriptEmbedding, VideoIndexStatus
from minio_utils import download_video

logger = logging.getLogger(__name__)


def extract_frames(video_path: str, interval_sec: float = 2.0, video_id_for_thumbs=None):
    """Extract frames from a video at a given interval.

    Yields (frame_num, timestamp_ms, pil_image) tuples.
    Skips dark/black frames (mean brightness < 15).
    Saves thumbnails to /data/thumbnails/{video_id}/ when video_id_for_thumbs is provided.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = int(fps * interval_sec)
    frame_idx = 0
    extracted = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            # Convert BGR -> RGB -> PIL
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)

            # Skip dark frames
            stat = ImageStat.Stat(pil_img.convert("L"))
            if stat.mean[0] < 15:
                frame_idx += 1
                continue

            timestamp_ms = int((frame_idx / fps) * 1000)

            # Save thumbnail JPEG for search result previews
            if video_id_for_thumbs:
                thumb_dir = os.path.join(settings.THUMBNAIL_DIR, str(video_id_for_thumbs))
                os.makedirs(thumb_dir, exist_ok=True)
                thumb_path = os.path.join(thumb_dir, f"{timestamp_ms}.jpg")
                pil_img.resize((320, int(320 * pil_img.height / pil_img.width))).save(
                    thumb_path, "JPEG", quality=75
                )

            yield (extracted, timestamp_ms, pil_img)
            extracted += 1

        frame_idx += 1

    cap.release()


def encode_frames_batch(frames, vision_model, preprocess, device):
    """Encode a batch of PIL images into embedding vectors using the vision model.

    Returns a numpy array of shape (N, embedding_dim).
    """
    if settings.VISION_MODEL_FAMILY == "hf_siglip":
        from main import vision_processor

        inputs = vision_processor(images=frames, return_tensors="pt").to(device)
        with torch.no_grad():
            features = vision_model.get_image_features(**inputs)
            if not isinstance(features, torch.Tensor):
                features = features.pooler_output
            features = torch.nn.functional.normalize(features, dim=-1)
        return features.cpu().float().numpy()

    tensors = torch.stack([preprocess(img) for img in frames]).to(device)

    with torch.no_grad():
        features = vision_model.encode_image(tensors)
        features = torch.nn.functional.normalize(features, dim=-1)

    return features.cpu().float().numpy()


_whisper_model = None


def _get_whisper_model():
    """Return a cached Whisper model instance (loaded once, reused across videos)."""
    global _whisper_model
    if _whisper_model is None:
        from pywhispercpp.model import Model as WhisperModel
        logger.info(f"Loading Whisper model: {settings.WHISPER_MODEL}")
        _whisper_model = WhisperModel(settings.WHISPER_MODEL)
    return _whisper_model


def transcribe_video(video_path: str):
    """Transcribe video audio using Whisper.

    Returns a list of dicts: [{text, start_ms, end_ms}, ...]
    """
    logger.info(f"Transcribing: {video_path}")
    model = _get_whisper_model()
    segments = model.transcribe(video_path)

    results = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        results.append({
            "text": text,
            "start_ms": int(seg.t0 * 10),  # pywhispercpp returns centiseconds
            "end_ms": int(seg.t1 * 10),
        })

    logger.info(f"Transcribed {len(results)} segments")
    return results


def encode_transcript_segments(segments, text_model):
    """Encode transcript segment texts into embedding vectors.

    Returns a numpy array of shape (N, embedding_dim).
    """
    if not segments:
        return np.array([])

    texts = [s["text"] for s in segments]
    embeddings = text_model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embeddings


def _store_frame_embeddings(video_id, all_frames, db, device):
    """Batch-encode frames with the vision model and insert into frame_embeddings.

    Acquires vision_lock per batch so search queries can interleave.
    Returns the number of frames stored.
    """
    import main as bridge_main

    frame_batch = []
    frame_meta = []
    for frame_num, timestamp_ms, pil_img in all_frames:
        frame_batch.append(pil_img)
        frame_meta.append((frame_num, timestamp_ms))

        if len(frame_batch) >= settings.BATCH_SIZE:
            with bridge_main.vision_lock:
                embeddings = encode_frames_batch(
                    frame_batch,
                    bridge_main.vision_model,
                    bridge_main.vision_preprocess,
                    device,
                )
            for i, (fn, ts) in enumerate(frame_meta):
                db.add(FrameEmbedding(
                    video_id=video_id, frame_num=fn,
                    timestamp_ms=ts, embedding=embeddings[i].tolist(),
                ))
            db.flush()
            frame_batch.clear()
            frame_meta.clear()

    if frame_batch:
        with bridge_main.vision_lock:
            embeddings = encode_frames_batch(
                frame_batch,
                bridge_main.vision_model,
                bridge_main.vision_preprocess,
                device,
            )
        for i, (fn, ts) in enumerate(frame_meta):
            db.add(FrameEmbedding(
                video_id=video_id, frame_num=fn,
                timestamp_ms=ts, embedding=embeddings[i].tolist(),
            ))
        db.flush()

    return db.query(FrameEmbedding).filter(
        FrameEmbedding.video_id == video_id
    ).count()


def _store_caption_embeddings(video_id, all_frames, db, device):
    """Caption frames and embed captions with text model.

    Returns the number of captions stored.
    """
    import time as _time
    import main as bridge_main
    from indexing.captioning import caption_frames_batch

    logger.info(f"Captioning {len(all_frames)} frames for {video_id} "
                f"(provider={settings.CAPTION_PROVIDER})")
    t0 = _time.perf_counter()
    captions = caption_frames_batch(
        all_frames,
        caption_model=bridge_main.caption_model,
        caption_processor=bridge_main.caption_processor,
        device=device,
    )
    t1 = _time.perf_counter()
    logger.info(f"Captioning took {t1-t0:.1f}s for {len(captions)} frames")

    if captions:
        caption_texts = [c[2] for c in captions]
        t2 = _time.perf_counter()
        with bridge_main.text_lock:
            caption_embs = bridge_main.text_model.encode(
                caption_texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
        t3 = _time.perf_counter()
        logger.info(f"Caption embedding took {t3-t2:.1f}s for {len(caption_texts)} texts")
        for i, (fn, ts, cap_text) in enumerate(captions):
            db.add(CaptionEmbedding(
                video_id=video_id, frame_num=fn,
                timestamp_ms=ts, caption_text=cap_text,
                embedding=caption_embs[i].tolist(),
            ))
        db.flush()

    return db.query(CaptionEmbedding).filter(
        CaptionEmbedding.video_id == video_id
    ).count()


def _store_transcript_embeddings(video_id, local_path, db):
    """Transcribe video and embed transcript segments.

    Returns the number of segments stored.
    """
    import main as bridge_main

    segments = transcribe_video(local_path)
    if segments:
        with bridge_main.text_lock:
            embeddings = encode_transcript_segments(segments, bridge_main.text_model)
        for i, seg in enumerate(segments):
            db.add(TranscriptEmbedding(
                video_id=video_id, segment_text=seg["text"],
                start_ms=seg["start_ms"], end_ms=seg["end_ms"],
                embedding=embeddings[i].tolist(),
            ))
        db.flush()

    return db.query(TranscriptEmbedding).filter(
        TranscriptEmbedding.video_id == video_id
    ).count()


def fix_video_indexes(video_id: str, object_name: str, db: Session):
    """Smart indexing pipeline: checks what exists and only generates what's missing.

    Queries the actual embedding tables to determine which indexes need work:
      - frame_embeddings   → visual
      - caption_embeddings → captions (skipped if CAPTION_ENABLED=false)
      - transcript_embeddings → transcript

    Downloads the video from MinIO only if something actually needs generating.
    This single function handles all indexing modes:
      - Fresh index (nothing exists)
      - Visual-only reindex (frame_embeddings deleted, rest intact)
      - Fix (fill in whatever's missing)
    """
    device = torch.device(settings.DEVICE)
    local_path = None

    try:
        job = (
            db.query(VideoIndexStatus)
            .filter(VideoIndexStatus.video_id == video_id)
            .first()
        )
        if not job:
            logger.error(f"No index job found for {video_id}")
            return

        job.status = "processing"
        job.error_message = None
        db.commit()

        # Check what actually exists in the DB
        has_visual = db.query(FrameEmbedding).filter(
            FrameEmbedding.video_id == video_id
        ).count()
        has_captions = db.query(CaptionEmbedding).filter(
            CaptionEmbedding.video_id == video_id
        ).count()
        has_transcript = db.query(TranscriptEmbedding).filter(
            TranscriptEmbedding.video_id == video_id
        ).count()

        # Use both the actual DB count AND the job flag to decide what's needed.
        # The flag means "we already ran this stage" — even if the result was 0 rows
        # (e.g. silent video → 0 transcript segments, all-black frames → 0 captions).
        need_visual = has_visual == 0 and not job.visual_indexed
        need_captions = (has_captions == 0 and not job.caption_indexed
                         and settings.CAPTION_ENABLED)
        need_transcript = has_transcript == 0 and not job.transcript_indexed
        need_frames = need_visual or need_captions  # frame extraction needed for both

        todo = []
        if need_visual:
            todo.append("visual")
        if need_captions:
            todo.append("captions")
        if need_transcript:
            todo.append("transcript")

        if not todo:
            logger.info(f"[fix] {video_id}: all indexes present, nothing to do")
            job.visual_indexed = True
            job.frame_count = has_visual
            if settings.CAPTION_ENABLED:
                job.caption_indexed = True
                job.caption_count = has_captions
            job.transcript_indexed = True
            job.segment_count = has_transcript
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            db.commit()
            return

        logger.info(f"[fix] {video_id}: need to generate {todo} "
                     f"(have visual={has_visual} captions={has_captions} transcript={has_transcript})")

        # Download video (needed for any generation)
        local_path = download_video(object_name, str(video_id))

        # Extract frames if visual or captions need them
        all_frames = None
        if need_frames:
            logger.info(f"[fix] Extracting frames for {video_id}")
            all_frames = list(extract_frames(
                local_path, settings.FRAME_INTERVAL_SEC, video_id_for_thumbs=video_id
            ))
            logger.info(f"[fix] Extracted {len(all_frames)} frames")

        # Stage 1: Visual embeddings
        if need_visual:
            frame_count = _store_frame_embeddings(video_id, all_frames, db, device)
            job.visual_indexed = True
            job.frame_count = frame_count
            db.commit()
            logger.info(f"[fix] Visual: stored {frame_count} frame embeddings")
        else:
            job.visual_indexed = True
            job.frame_count = has_visual

        # Stage 2: Caption embeddings
        if need_captions:
            caption_count = _store_caption_embeddings(video_id, all_frames, db, device)
            job.caption_indexed = True
            job.caption_count = caption_count
            db.commit()
            logger.info(f"[fix] Captions: stored {caption_count} caption embeddings")
        elif settings.CAPTION_ENABLED:
            job.caption_indexed = True
            job.caption_count = has_captions

        # Stage 3: Transcript embeddings
        if need_transcript:
            segment_count = _store_transcript_embeddings(video_id, local_path, db)
            job.transcript_indexed = True
            job.segment_count = segment_count
            db.commit()
            logger.info(f"[fix] Transcript: stored {segment_count} segments")
        else:
            job.transcript_indexed = True
            job.segment_count = has_transcript

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.info(f"[fix] Complete for {video_id}")

    except Exception as e:
        logger.error(f"[fix] Failed for {video_id}: {e}", exc_info=True)
        db.rollback()
        try:
            job = (
                db.query(VideoIndexStatus)
                .filter(VideoIndexStatus.video_id == video_id)
                .first()
            )
            if job:
                job.status = "failed"
                job.error_message = str(e)[:2000]
                db.commit()
        except Exception:
            logger.error("Failed to update job status after error", exc_info=True)

    finally:
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
                logger.info(f"Cleaned up temp file: {local_path}")
            except OSError:
                pass


# Legacy aliases — route everything through fix_video_indexes
def index_video(video_id: str, object_name: str, db: Session):
    """Full indexing pipeline for a single video."""
    return fix_video_indexes(video_id, object_name, db)


def reindex_visual_video(video_id: str, object_name: str, db: Session):
    """Visual-only reindex (frame_embeddings already deleted by endpoint)."""
    return fix_video_indexes(video_id, object_name, db)
