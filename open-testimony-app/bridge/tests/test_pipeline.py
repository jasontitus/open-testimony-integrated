"""Tests for the indexing pipeline logic."""
import os
import sys
import tempfile
import uuid
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFrameExtraction:
    """Tests for extract_frames()."""

    def test_extract_frames_from_video(self, tmp_path):
        """extract_frames yields frames at the specified interval."""
        import cv2

        # Create a small test video (10 frames of solid color)
        video_path = str(tmp_path / "test.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(video_path, fourcc, 10.0, (64, 64))
        for i in range(30):  # 3 seconds at 10fps
            frame = np.full((64, 64, 3), fill_value=128, dtype=np.uint8)
            writer.write(frame)
        writer.release()

        from indexing.pipeline import extract_frames

        frames = list(extract_frames(video_path, interval_sec=1.0))

        # At 10fps with 1sec interval, we expect ~3 frames from 3 seconds
        assert len(frames) >= 2
        for frame_num, timestamp_ms, pil_img in frames:
            assert isinstance(frame_num, int)
            assert isinstance(timestamp_ms, int)
            assert timestamp_ms >= 0
            assert pil_img.mode == "RGB"

    def test_dark_frames_skipped(self, tmp_path):
        """extract_frames skips dark/black frames."""
        import cv2

        video_path = str(tmp_path / "dark.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(video_path, fourcc, 10.0, (64, 64))
        for _ in range(10):
            # All-black frames (brightness < 15)
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            writer.write(frame)
        writer.release()

        from indexing.pipeline import extract_frames

        frames = list(extract_frames(video_path, interval_sec=0.5))
        assert len(frames) == 0

    def test_invalid_video_path_raises(self):
        """extract_frames raises on invalid video path."""
        from indexing.pipeline import extract_frames

        with pytest.raises(RuntimeError, match="Cannot open"):
            list(extract_frames("/nonexistent/video.mp4"))


class TestEncodeFramesBatch:
    """Tests for encode_frames_batch()."""

    def test_encode_returns_correct_shape(
        self, mock_vision_model, mock_vision_preprocess
    ):
        """Batch encoding returns (N, embedding_dim) numpy array."""
        import torch
        from PIL import Image
        from indexing.pipeline import encode_frames_batch

        frames = [Image.new("RGB", (64, 64), color="red") for _ in range(4)]

        with patch("indexing.pipeline.settings") as mock_settings:
            mock_settings.VISION_MODEL_FAMILY = "open_clip"
            mock_settings.DEVICE = "cpu"
            embeddings = encode_frames_batch(
                frames,
                mock_vision_model,
                mock_vision_preprocess,
                torch.device("cpu"),
            )

        assert embeddings.shape == (4, 768)
        assert embeddings.dtype == np.float32

    def test_embeddings_normalized(
        self, mock_vision_model, mock_vision_preprocess
    ):
        """Embeddings are L2-normalized."""
        import torch
        from PIL import Image
        from indexing.pipeline import encode_frames_batch

        frames = [Image.new("RGB", (64, 64))]

        with patch("indexing.pipeline.settings") as mock_settings:
            mock_settings.VISION_MODEL_FAMILY = "open_clip"
            mock_settings.DEVICE = "cpu"
            embeddings = encode_frames_batch(
                frames,
                mock_vision_model,
                mock_vision_preprocess,
                torch.device("cpu"),
            )

        norms = np.linalg.norm(embeddings, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=0.01)


class TestTranscriptEncoding:
    """Tests for encode_transcript_segments()."""

    def test_encode_segments(self, mock_text_model):
        """Transcript segments are encoded to correct shape."""
        from indexing.pipeline import encode_transcript_segments

        segments = [
            {"text": "hello world"},
            {"text": "this is a test"},
            {"text": "another segment"},
        ]

        embeddings = encode_transcript_segments(segments, mock_text_model)

        assert embeddings.shape == (3, 4096)
        mock_text_model.encode.assert_called_once()
        call_kwargs = mock_text_model.encode.call_args
        assert call_kwargs.kwargs["normalize_embeddings"] is True

    def test_encode_empty_segments(self, mock_text_model):
        """Empty segment list returns empty array."""
        from indexing.pipeline import encode_transcript_segments

        embeddings = encode_transcript_segments([], mock_text_model)
        assert len(embeddings) == 0


class TestFullPipeline:
    """Integration test for index_video()."""

    def test_pipeline_updates_status_on_failure(self, db_session):
        """Pipeline marks job as failed when MinIO download fails."""
        from indexing.pipeline import index_video
        from models import VideoIndexStatus

        vid = str(uuid.uuid4())
        # Insert video stub
        from tests.conftest import insert_video_stub

        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        db_session.add(
            VideoIndexStatus(
                video_id=video_uuid,
                object_name="videos/nonexistent.mp4",
                status="pending",
            )
        )
        db_session.commit()

        # Mock the download to fail
        with patch("indexing.pipeline.download_video", side_effect=Exception("MinIO unreachable")):
            import main as bridge_main
            bridge_main.vision_model = MagicMock()
            bridge_main.text_model = MagicMock()

            index_video(video_uuid, "videos/nonexistent.mp4", db_session)

        db_session.expire_all()
        job = (
            db_session.query(VideoIndexStatus)
            .filter(VideoIndexStatus.video_id == video_uuid)
            .first()
        )
        assert job.status == "failed"
        assert "MinIO unreachable" in job.error_message
