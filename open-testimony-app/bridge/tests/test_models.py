"""Tests for SQLAlchemy models (pgvector tables)."""
import os
import sys
import uuid

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import FrameEmbedding, TranscriptEmbedding, VideoIndexStatus
from tests.conftest import insert_video_stub


class TestFrameEmbeddingModel:
    """FrameEmbedding table operations."""

    def test_insert_and_query(self, db_session):
        """Can insert and retrieve frame embeddings."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        emb = FrameEmbedding(
            video_id=video_uuid,
            frame_num=0,
            timestamp_ms=2000,
            embedding=np.random.randn(768).tolist(),
        )
        db_session.add(emb)
        db_session.commit()

        result = (
            db_session.query(FrameEmbedding)
            .filter(FrameEmbedding.video_id == video_uuid)
            .first()
        )
        assert result is not None
        assert result.frame_num == 0
        assert result.timestamp_ms == 2000
        assert len(result.embedding) == 768

    def test_multiple_frames_per_video(self, db_session):
        """Multiple frames can be stored per video."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        for i in range(10):
            db_session.add(
                FrameEmbedding(
                    video_id=video_uuid,
                    frame_num=i,
                    timestamp_ms=i * 2000,
                    embedding=np.random.randn(768).tolist(),
                )
            )
        db_session.commit()

        count = (
            db_session.query(FrameEmbedding)
            .filter(FrameEmbedding.video_id == video_uuid)
            .count()
        )
        assert count == 10


class TestTranscriptEmbeddingModel:
    """TranscriptEmbedding table operations."""

    def test_insert_and_query(self, db_session):
        """Can insert and retrieve transcript embeddings."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        emb = TranscriptEmbedding(
            video_id=video_uuid,
            segment_text="The witness stated that...",
            start_ms=0,
            end_ms=3000,
            embedding=np.random.randn(4096).tolist(),
        )
        db_session.add(emb)
        db_session.commit()

        result = (
            db_session.query(TranscriptEmbedding)
            .filter(TranscriptEmbedding.video_id == video_uuid)
            .first()
        )
        assert result is not None
        assert "witness" in result.segment_text
        assert result.start_ms == 0
        assert result.end_ms == 3000
        assert len(result.embedding) == 4096

    def test_segment_text_preserved(self, db_session):
        """Long segment text is stored and retrieved correctly."""
        vid = insert_video_stub(db_session)
        long_text = "word " * 200  # ~1000 chars

        db_session.add(
            TranscriptEmbedding(
                video_id=uuid.UUID(vid),
                segment_text=long_text.strip(),
                start_ms=0,
                end_ms=60000,
                embedding=np.random.randn(4096).tolist(),
            )
        )
        db_session.commit()

        result = db_session.query(TranscriptEmbedding).first()
        assert result.segment_text == long_text.strip()


class TestVideoIndexStatusModel:
    """VideoIndexStatus table operations."""

    def test_create_pending_job(self, db_session):
        """Can create a pending indexing job."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        job = VideoIndexStatus(
            video_id=video_uuid,
            object_name="videos/test/vid.mp4",
            status="pending",
        )
        db_session.add(job)
        db_session.commit()

        result = (
            db_session.query(VideoIndexStatus)
            .filter(VideoIndexStatus.video_id == video_uuid)
            .first()
        )
        assert result.status == "pending"
        assert result.visual_indexed is False
        assert result.transcript_indexed is False
        assert result.frame_count is None
        assert result.segment_count is None

    def test_unique_video_id_constraint(self, db_session):
        """Only one indexing job per video_id."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        db_session.add(
            VideoIndexStatus(
                video_id=video_uuid,
                object_name="videos/test/vid.mp4",
                status="pending",
            )
        )
        db_session.commit()

        # Second insert with same video_id should fail
        from sqlalchemy.exc import IntegrityError

        db_session.add(
            VideoIndexStatus(
                video_id=video_uuid,
                object_name="videos/test/vid2.mp4",
                status="pending",
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_status_transitions(self, db_session):
        """Job status can be updated through the lifecycle."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        job = VideoIndexStatus(
            video_id=video_uuid,
            object_name="videos/test/vid.mp4",
            status="pending",
        )
        db_session.add(job)
        db_session.commit()

        # pending -> processing
        job.status = "processing"
        db_session.commit()
        db_session.expire_all()
        assert (
            db_session.query(VideoIndexStatus)
            .filter(VideoIndexStatus.video_id == video_uuid)
            .first()
            .status
            == "processing"
        )

        # processing -> completed
        from datetime import datetime

        job.status = "completed"
        job.visual_indexed = True
        job.transcript_indexed = True
        job.frame_count = 50
        job.segment_count = 12
        job.completed_at = datetime.utcnow()
        db_session.commit()
        db_session.expire_all()

        final = (
            db_session.query(VideoIndexStatus)
            .filter(VideoIndexStatus.video_id == video_uuid)
            .first()
        )
        assert final.status == "completed"
        assert final.frame_count == 50
        assert final.completed_at is not None


# Need pytest import for raises
import pytest
