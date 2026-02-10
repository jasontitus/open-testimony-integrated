"""Tests for the video-uploaded webhook endpoint."""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import VideoIndexStatus
from tests.conftest import insert_video_stub


class TestVideoUploadedWebhook:
    """POST /hooks/video-uploaded creates indexing jobs."""

    def test_webhook_creates_pending_job(self, client, db_session):
        """Webhook creates a pending VideoIndexStatus row."""
        vid = insert_video_stub(db_session)

        resp = client.post(
            "/hooks/video-uploaded",
            json={"video_id": vid, "object_name": "videos/dev/test.mp4"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"
        assert body["video_id"] == vid

        job = (
            db_session.query(VideoIndexStatus)
            .filter(VideoIndexStatus.video_id == uuid.UUID(vid))
            .first()
        )
        assert job is not None
        assert job.status == "pending"
        assert job.object_name == "videos/dev/test.mp4"
        assert job.visual_indexed is False
        assert job.transcript_indexed is False

    def test_webhook_idempotent(self, client, db_session):
        """Sending the webhook twice for the same video doesn't create duplicates."""
        vid = insert_video_stub(db_session)

        resp1 = client.post(
            "/hooks/video-uploaded",
            json={"video_id": vid, "object_name": "videos/dev/test.mp4"},
        )
        resp2 = client.post(
            "/hooks/video-uploaded",
            json={"video_id": vid, "object_name": "videos/dev/test.mp4"},
        )

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "already_queued"

        count = (
            db_session.query(VideoIndexStatus)
            .filter(VideoIndexStatus.video_id == uuid.UUID(vid))
            .count()
        )
        assert count == 1

    def test_webhook_missing_fields(self, client):
        """Webhook with missing fields returns 422."""
        resp = client.post(
            "/hooks/video-uploaded",
            json={"video_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 422

    def test_webhook_invalid_uuid(self, client):
        """Webhook with invalid UUID returns 422."""
        resp = client.post(
            "/hooks/video-uploaded",
            json={"video_id": "not-a-uuid", "object_name": "test.mp4"},
        )
        assert resp.status_code == 422
