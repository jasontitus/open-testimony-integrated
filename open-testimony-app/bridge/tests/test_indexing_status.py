"""Tests for indexing status and reindex endpoints."""
import os
import sys
import uuid
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import FrameEmbedding, TranscriptEmbedding, VideoIndexStatus
from tests.conftest import insert_video_stub


class TestIndexingOverview:
    """GET /indexing/status returns aggregate counts."""

    def test_empty_overview(self, client, auth_cookie):
        """Returns zero counts when no jobs exist."""
        resp = client.get("/indexing/status", cookies=auth_cookie)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["pending"] == 0
        assert body["completed"] == 0

    def test_overview_counts(self, client, auth_cookie, db_session):
        """Returns correct counts for each status."""
        for status in ["pending", "pending", "completed", "processing", "failed"]:
            vid = insert_video_stub(db_session)
            db_session.add(
                VideoIndexStatus(
                    video_id=uuid.UUID(vid),
                    object_name=f"videos/test/{vid}.mp4",
                    status=status,
                )
            )
        db_session.commit()

        resp = client.get("/indexing/status", cookies=auth_cookie)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert body["pending"] == 2
        assert body["completed"] == 1
        assert body["processing"] == 1
        assert body["failed"] == 1


class TestIndexingStatusPerVideo:
    """GET /indexing/status/{video_id} returns per-video status."""

    def test_existing_job(self, client, auth_cookie, db_session):
        """Returns full status for an indexed video."""
        vid = insert_video_stub(db_session)
        db_session.add(
            VideoIndexStatus(
                video_id=uuid.UUID(vid),
                object_name="videos/test/vid.mp4",
                status="completed",
                visual_indexed=True,
                transcript_indexed=True,
                frame_count=42,
                segment_count=7,
                completed_at=datetime.utcnow(),
            )
        )
        db_session.commit()

        resp = client.get(f"/indexing/status/{vid}", cookies=auth_cookie)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["frame_count"] == 42
        assert body["segment_count"] == 7
        assert body["visual_indexed"] is True
        assert body["transcript_indexed"] is True
        assert body["completed_at"] is not None

    def test_nonexistent_video(self, client, auth_cookie):
        """Returns 404 for a video with no indexing job."""
        resp = client.get(
            f"/indexing/status/{uuid.uuid4()}", cookies=auth_cookie
        )
        assert resp.status_code == 404

    def test_failed_job_shows_error(self, client, auth_cookie, db_session):
        """A failed job includes the error message."""
        vid = insert_video_stub(db_session)
        db_session.add(
            VideoIndexStatus(
                video_id=uuid.UUID(vid),
                object_name="videos/test/vid.mp4",
                status="failed",
                error_message="CUDA out of memory",
            )
        )
        db_session.commit()

        resp = client.get(f"/indexing/status/{vid}", cookies=auth_cookie)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert "CUDA" in body["error_message"]


class TestReindex:
    """POST /indexing/reindex/{video_id} resets a video for re-indexing."""

    def test_reindex_clears_embeddings(self, client, auth_cookie, db_session):
        """Reindexing deletes existing embeddings and resets job to pending."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        # Create completed job with embeddings
        db_session.add(
            VideoIndexStatus(
                video_id=video_uuid,
                object_name="videos/test/vid.mp4",
                status="completed",
                visual_indexed=True,
                transcript_indexed=True,
                frame_count=2,
                segment_count=1,
            )
        )
        db_session.add(
            FrameEmbedding(
                video_id=video_uuid,
                frame_num=0,
                timestamp_ms=0,
                embedding=np.random.randn(1280).tolist(),
            )
        )
        db_session.add(
            TranscriptEmbedding(
                video_id=video_uuid,
                segment_text="hello world",
                start_ms=0,
                end_ms=1000,
                embedding=np.random.randn(4096).tolist(),
            )
        )
        db_session.commit()

        resp = client.post(f"/indexing/reindex/{vid}", cookies=auth_cookie)
        assert resp.status_code == 200
        assert resp.json()["status"] == "reindex_queued"

        # Verify embeddings were deleted
        db_session.expire_all()
        assert (
            db_session.query(FrameEmbedding)
            .filter(FrameEmbedding.video_id == video_uuid)
            .count()
            == 0
        )
        assert (
            db_session.query(TranscriptEmbedding)
            .filter(TranscriptEmbedding.video_id == video_uuid)
            .count()
            == 0
        )

        # Verify job reset
        job = (
            db_session.query(VideoIndexStatus)
            .filter(VideoIndexStatus.video_id == video_uuid)
            .first()
        )
        assert job.status == "pending"
        assert job.visual_indexed is False
        assert job.transcript_indexed is False
        assert job.frame_count is None

    def test_reindex_nonexistent(self, client, auth_cookie):
        """Reindexing a nonexistent video returns 404."""
        resp = client.post(
            f"/indexing/reindex/{uuid.uuid4()}", cookies=auth_cookie
        )
        assert resp.status_code == 404


class TestReindexAll:
    """POST /indexing/reindex-all resets all videos."""

    def test_reindex_all(self, client, auth_cookie, db_session):
        """Reindex-all resets all jobs to pending and clears embeddings."""
        vids = []
        for _ in range(3):
            vid = insert_video_stub(db_session)
            vids.append(vid)
            db_session.add(
                VideoIndexStatus(
                    video_id=uuid.UUID(vid),
                    object_name=f"videos/test/{vid}.mp4",
                    status="completed",
                    visual_indexed=True,
                    frame_count=5,
                )
            )
        db_session.commit()

        resp = client.post("/indexing/reindex-all", cookies=auth_cookie)
        assert resp.status_code == 200
        assert resp.json()["count"] == 3

        db_session.expire_all()
        for vid in vids:
            job = (
                db_session.query(VideoIndexStatus)
                .filter(VideoIndexStatus.video_id == uuid.UUID(vid))
                .first()
            )
            assert job.status == "pending"
