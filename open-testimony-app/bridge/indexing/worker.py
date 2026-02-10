"""Background worker that polls for pending indexing jobs and processes them."""
import asyncio
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from models import VideoIndexStatus
from indexing.pipeline import index_video

logger = logging.getLogger(__name__)

# Separate engine for the worker (avoids sharing sessions across async boundaries)
worker_engine = create_engine(settings.DATABASE_URL)
WorkerSession = sessionmaker(bind=worker_engine)


async def indexing_worker():
    """Continuously poll for pending indexing jobs and process them."""
    logger.info("Indexing worker started, polling every %ds", settings.WORKER_POLL_INTERVAL)

    while True:
        try:
            db = WorkerSession()
            try:
                job = (
                    db.query(VideoIndexStatus)
                    .filter(VideoIndexStatus.status == "pending")
                    .order_by(VideoIndexStatus.created_at.asc())
                    .first()
                )

                if job:
                    logger.info(
                        f"Processing indexing job: video_id={job.video_id}, "
                        f"object_name={job.object_name}"
                    )
                    # Run the CPU/GPU-heavy pipeline in a thread pool
                    await asyncio.to_thread(
                        index_video,
                        job.video_id,
                        job.object_name,
                        db,
                    )
                else:
                    pass  # No pending jobs

            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("Indexing worker cancelled")
            raise
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)

        await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
