"""MinIO utilities for downloading videos to temp files."""
import logging
import os

from minio import Minio

from config import settings

logger = logging.getLogger(__name__)


def get_minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def download_video(object_name: str, video_id: str) -> str:
    """Download a video from MinIO to a local temp file.

    Returns the path to the downloaded file.
    """
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    ext = os.path.splitext(object_name)[1] or ".mp4"
    local_path = os.path.join(settings.TEMP_DIR, f"{video_id}{ext}")

    client = get_minio_client()
    client.fget_object(settings.MINIO_BUCKET, object_name, local_path)
    logger.info(f"Downloaded {object_name} -> {local_path}")
    return local_path
