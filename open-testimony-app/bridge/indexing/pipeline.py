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
from models import FrameEmbedding, TranscriptEmbedding, VideoIndexStatus
from minio_utils import download_video

logger = logging.getLogger(__name__)


def extract_frames(video_path: str, interval_sec: float = 2.0):
    """Extract frames from a video at a given interval.

    Yields (frame_num, timestamp_ms, pil_image) tuples.
    Skips dark/black frames (mean brightness < 15).
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
            yield (extracted, timestamp_ms, pil_img)
            extracted += 1

        frame_idx += 1

    cap.release()


def encode_frames_batch(frames, vision_model, preprocess, device):
    """Encode a batch of PIL images into embedding vectors using the vision model.

    Returns a numpy array of shape (N, embedding_dim).
    """
    import open_clip

    tensors = torch.stack([preprocess(img) for img in frames]).to(device)

    with torch.no_grad():
        if settings.VISION_MODEL_FAMILY == "open_clip":
            features = vision_model.encode_image(tensors)
            features = torch.nn.functional.normalize(features, dim=-1)
        else:
            features, _, _ = vision_model(tensors, None)
            features = torch.nn.functional.normalize(features, dim=-1)

    return features.cpu().float().numpy()


def transcribe_video(video_path: str):
    """Transcribe video audio using Whisper.

    Returns a list of dicts: [{text, start_ms, end_ms}, ...]
    """
    from pywhispercpp.model import Model as WhisperModel

    logger.info(f"Transcribing: {video_path}")
    model = WhisperModel(settings.WHISPER_MODEL)
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


def index_video(video_id: str, object_name: str, db: Session):
    """Full indexing pipeline for a single video.

    1. Download from MinIO
    2. Extract & encode frames -> INSERT frame_embeddings
    3. Transcribe & encode segments -> INSERT transcript_embeddings
    4. Update video_index_status
    """
    import main as bridge_main

    device = torch.device(settings.DEVICE)
    local_path = None

    try:
        # Mark as processing
        job = (
            db.query(VideoIndexStatus)
            .filter(VideoIndexStatus.video_id == video_id)
            .first()
        )
        if not job:
            logger.error(f"No index job found for {video_id}")
            return
        job.status = "processing"
        db.commit()

        # 1. Download video from MinIO
        local_path = download_video(object_name, str(video_id))

        # 2. Extract and encode frames
        logger.info(f"Extracting frames for {video_id}")
        frame_batch = []
        frame_meta = []

        for frame_num, timestamp_ms, pil_img in extract_frames(
            local_path, settings.FRAME_INTERVAL_SEC
        ):
            frame_batch.append(pil_img)
            frame_meta.append((frame_num, timestamp_ms))

            if len(frame_batch) >= settings.BATCH_SIZE:
                embeddings = encode_frames_batch(
                    frame_batch,
                    bridge_main.vision_model,
                    bridge_main.vision_preprocess,
                    device,
                )
                for i, (fn, ts) in enumerate(frame_meta):
                    db.add(
                        FrameEmbedding(
                            video_id=video_id,
                            frame_num=fn,
                            timestamp_ms=ts,
                            embedding=embeddings[i].tolist(),
                        )
                    )
                db.flush()
                frame_batch.clear()
                frame_meta.clear()

        # Final partial batch
        if frame_batch:
            embeddings = encode_frames_batch(
                frame_batch,
                bridge_main.vision_model,
                bridge_main.vision_preprocess,
                device,
            )
            for i, (fn, ts) in enumerate(frame_meta):
                db.add(
                    FrameEmbedding(
                        video_id=video_id,
                        frame_num=fn,
                        timestamp_ms=ts,
                        embedding=embeddings[i].tolist(),
                    )
                )
            db.flush()

        total_frames = sum(1 for _ in [])  # already inserted above
        frame_count = (
            db.query(FrameEmbedding)
            .filter(FrameEmbedding.video_id == video_id)
            .count()
        )
        job.visual_indexed = True
        job.frame_count = frame_count
        db.commit()
        logger.info(f"Indexed {frame_count} frames for {video_id}")

        # 3. Transcribe and encode transcript segments
        segments = transcribe_video(local_path)
        if segments:
            embeddings = encode_transcript_segments(
                segments, bridge_main.text_model
            )
            for i, seg in enumerate(segments):
                db.add(
                    TranscriptEmbedding(
                        video_id=video_id,
                        segment_text=seg["text"],
                        start_ms=seg["start_ms"],
                        end_ms=seg["end_ms"],
                        embedding=embeddings[i].tolist(),
                    )
                )
            db.flush()

        segment_count = (
            db.query(TranscriptEmbedding)
            .filter(TranscriptEmbedding.video_id == video_id)
            .count()
        )
        job.transcript_indexed = True
        job.segment_count = segment_count
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.info(
            f"Indexing complete for {video_id}: "
            f"{frame_count} frames, {segment_count} segments"
        )

    except Exception as e:
        logger.error(f"Indexing failed for {video_id}: {e}", exc_info=True)
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
        # Clean up temp file
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
                logger.info(f"Cleaned up temp file: {local_path}")
            except OSError:
                pass
