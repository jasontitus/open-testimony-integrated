"""Background worker that polls for pending indexing jobs and processes them."""
import asyncio
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from models import VideoIndexStatus
from indexing.pipeline import fix_video_indexes

logger = logging.getLogger(__name__)

# Separate engine for the worker (avoids sharing sessions across async boundaries)
worker_engine = create_engine(settings.DATABASE_URL)
WorkerSession = sessionmaker(bind=worker_engine)

# All statuses that mean "this video needs work"
PENDING_STATUSES = ("pending", "pending_visual", "pending_fix")


async def indexing_worker():
    """Continuously poll for pending indexing jobs and process them."""
    logger.info("Indexing worker started, polling every %ds", settings.WORKER_POLL_INTERVAL)

    while True:
        try:
            db = WorkerSession()
            try:
                job = (
                    db.query(VideoIndexStatus)
                    .filter(VideoIndexStatus.status.in_(PENDING_STATUSES))
                    .order_by(VideoIndexStatus.created_at.asc())
                    .first()
                )

                if job:
                    logger.info(
                        f"Processing job ({job.status}): video_id={job.video_id}, "
                        f"object_name={job.object_name}"
                    )
                    await asyncio.to_thread(
                        fix_video_indexes,
                        job.video_id,
                        job.object_name,
                        db,
                    )

            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("Indexing worker cancelled")
            raise
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)

        await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
