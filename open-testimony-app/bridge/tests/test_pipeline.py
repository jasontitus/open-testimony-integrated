"""Tests for the indexing pipeline logic."""
import os
import sys
import tempfile
import uuid
from unittest.mock import patch, MagicMock

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFrameExtraction:
    """Tests for extract_frames()."""

    def test_extract_frames_from_video(self):
        """extract_frames yields frames at the specified interval."""
        from indexing.pipeline import extract_frames

        # Mock cv2.VideoCapture to return bright frames
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 10.0  # 10 fps

        bright_frame = np.full((64, 64, 3), fill_value=128, dtype=np.uint8)
        # 30 frames at 10fps = 3 seconds; return True 30 times, then False
        mock_cap.read.side_effect = [(True, bright_frame)] * 30 + [(False, None)]

        with patch("indexing.pipeline.cv2") as mock_cv2:
            mock_cv2.VideoCapture.return_value = mock_cap
            mock_cv2.CAP_PROP_FPS = 5  # cv2.CAP_PROP_FPS constant
            mock_cv2.COLOR_BGR2RGB = 4  # cv2.COLOR_BGR2RGB constant
            mock_cv2.cvtColor.side_effect = lambda frame, code: frame  # passthrough

            frames = list(extract_frames("/fake/video.mp4", interval_sec=1.0))

        # At 10fps with 1sec interval, we expect ~3 frames from 3 seconds
        assert len(frames) >= 2
        for frame_num, timestamp_ms, pil_img in frames:
            assert isinstance(frame_num, int)
            assert isinstance(timestamp_ms, int)
            assert timestamp_ms >= 0
            assert pil_img.mode == "RGB"

    def test_dark_frames_skipped(self):
        """extract_frames skips dark/black frames."""
        from indexing.pipeline import extract_frames

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 10.0

        dark_frame = np.zeros((64, 64, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [(True, dark_frame)] * 10 + [(False, None)]

        with patch("indexing.pipeline.cv2") as mock_cv2:
            mock_cv2.VideoCapture.return_value = mock_cap
            mock_cv2.CAP_PROP_FPS = 5
            mock_cv2.COLOR_BGR2RGB = 4
            mock_cv2.cvtColor.side_effect = lambda frame, code: frame

            frames = list(extract_frames("/fake/video.mp4", interval_sec=0.5))

        assert len(frames) == 0

    def test_invalid_video_path_raises(self):
        """extract_frames raises on invalid video path when cap fails."""
        from indexing.pipeline import extract_frames

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False

        with patch("indexing.pipeline.cv2") as mock_cv2:
            mock_cv2.VideoCapture.return_value = mock_cap
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

        with patch("indexing.pipeline.settings") as mock_settings:
            mock_settings.VISION_MODEL_FAMILY = "open_clip"
            mock_settings.DEVICE = "cpu"

            frames = [Image.new("RGB", (64, 64), color="red") for _ in range(4)]
            embeddings = encode_frames_batch(
                frames,
                mock_vision_model,
                mock_vision_preprocess,
                torch.device("cpu"),
            )

        assert embeddings.shape == (4, 1152)
        assert embeddings.itemsize == 4  # float32 = 4 bytes

    def test_embeddings_normalized(
        self, mock_vision_model, mock_vision_preprocess
    ):
        """Embeddings are L2-normalized."""
        import torch
        from PIL import Image
        from indexing.pipeline import encode_frames_batch

        with patch("indexing.pipeline.settings") as mock_settings:
            mock_settings.VISION_MODEL_FAMILY = "open_clip"
            mock_settings.DEVICE = "cpu"

            frames = [Image.new("RGB", (64, 64))]
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


class TestIsPhoto:
    """Tests for is_photo() media type detection."""

    def test_photos_prefix_detected(self):
        """Objects under photos/ are detected as photos."""
        from indexing.pipeline import is_photo

        assert is_photo("photos/device-1/20260213_120000_img.jpg") is True
        assert is_photo("photos/bulk/20260213_120000_img.png") is True

    def test_videos_prefix_not_photo(self):
        """Objects under videos/ are not detected as photos."""
        from indexing.pipeline import is_photo

        assert is_photo("videos/device-1/20260213_120000_clip.mp4") is False
        assert is_photo("videos/bulk/20260213_120000_clip.mov") is False

    def test_photo_extensions_detected(self):
        """Common photo extensions are detected regardless of path prefix."""
        from indexing.pipeline import is_photo

        for ext in [".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tiff", ".bmp", ".gif"]:
            assert is_photo(f"other/path/image{ext}") is True, f"Failed for {ext}"

    def test_video_extensions_not_photo(self):
        """Video extensions under non-photos/ paths are not detected as photos."""
        from indexing.pipeline import is_photo

        for ext in [".mp4", ".mov", ".avi", ".mkv"]:
            assert is_photo(f"other/path/clip{ext}") is False, f"Failed for {ext}"

    def test_case_insensitive_extensions(self):
        """Extension matching is case-insensitive."""
        from indexing.pipeline import is_photo

        assert is_photo("other/IMG_001.JPG") is True
        assert is_photo("other/IMG_001.Jpeg") is True


class TestPhotoFrameExtraction:
    """Tests for extract_photo_frame()."""

    def test_extracts_single_frame(self):
        """extract_photo_frame returns exactly one frame tuple."""
        from indexing.pipeline import extract_photo_frame

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            Image.new("RGB", (100, 80), color="blue").save(f, "JPEG")
            f.flush()
            tmp_path = f.name

        try:
            frames = extract_photo_frame(tmp_path)
            assert len(frames) == 1
        finally:
            os.unlink(tmp_path)

    def test_frame_format_matches_video(self):
        """Returned tuple has (frame_num=0, timestamp_ms=0, pil_image) format."""
        from indexing.pipeline import extract_photo_frame

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            Image.new("RGB", (64, 48), color="green").save(f, "PNG")
            f.flush()
            tmp_path = f.name

        try:
            frames = extract_photo_frame(tmp_path)
            frame_num, timestamp_ms, pil_img = frames[0]

            assert frame_num == 0
            assert timestamp_ms == 0
            assert isinstance(pil_img, Image.Image)
            assert pil_img.mode == "RGB"
        finally:
            os.unlink(tmp_path)

    def test_creates_thumbnail(self):
        """Thumbnail is saved when video_id_for_thumbs is provided."""
        from indexing.pipeline import extract_photo_frame

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            Image.new("RGB", (640, 480), color="red").save(f, "JPEG")
            f.flush()
            tmp_path = f.name

        thumb_dir = tempfile.mkdtemp()
        fake_id = "test-photo-thumb-id"

        try:
            with patch("indexing.pipeline.settings") as mock_settings:
                mock_settings.THUMBNAIL_DIR = thumb_dir
                frames = extract_photo_frame(tmp_path, video_id_for_thumbs=fake_id)

            assert len(frames) == 1
            expected_thumb = os.path.join(thumb_dir, fake_id, "0.jpg")
            assert os.path.exists(expected_thumb)

            # Verify thumbnail is a valid JPEG
            thumb_img = Image.open(expected_thumb)
            assert thumb_img.width == 320
        finally:
            os.unlink(tmp_path)
            import shutil
            shutil.rmtree(thumb_dir, ignore_errors=True)

    def test_dark_photo_still_indexed(self):
        """Very dark photos are logged as warning but still returned."""
        from indexing.pipeline import extract_photo_frame

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Create a nearly-black image (mean brightness < 15)
            Image.new("RGB", (64, 64), color=(5, 5, 5)).save(f, "PNG")
            f.flush()
            tmp_path = f.name

        try:
            frames = extract_photo_frame(tmp_path)
            assert len(frames) == 1
        finally:
            os.unlink(tmp_path)


class TestPhotoIndexingPipeline:
    """Integration tests for photo indexing through fix_video_indexes()."""

    def test_photo_skips_transcript_and_clips(self, db_session):
        """Photos mark transcript/clips as indexed without running those stages."""
        from indexing.pipeline import fix_video_indexes
        from models import VideoIndexStatus, FrameEmbedding, TranscriptEmbedding, ClipEmbedding
        from tests.conftest import insert_video_stub

        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        db_session.add(VideoIndexStatus(
            video_id=video_uuid,
            object_name="photos/device-1/20260213_photo.jpg",
            status="pending",
        ))
        db_session.commit()

        # Create a real temp photo for extract_photo_frame
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            Image.new("RGB", (64, 64), color="blue").save(f, "JPEG")
            tmp_path = f.name

        try:
            with patch("indexing.pipeline.download_video", return_value=tmp_path), \
                 patch("indexing.pipeline._store_frame_embeddings", return_value=1) as mock_visual, \
                 patch("indexing.pipeline._store_caption_embeddings", return_value=1) as mock_captions, \
                 patch("indexing.pipeline._store_transcript_embeddings") as mock_transcript, \
                 patch("indexing.pipeline._store_clip_embeddings") as mock_clips, \
                 patch("indexing.pipeline._store_face_detections", return_value=0) as mock_faces, \
                 patch("indexing.pipeline.settings") as mock_settings:
                mock_settings.CAPTION_ENABLED = True
                mock_settings.CLIP_ENABLED = True
                mock_settings.FACE_CLUSTERING_ENABLED = True
                mock_settings.DEVICE = "cpu"
                mock_settings.FRAME_INTERVAL_SEC = 2.0
                mock_settings.THUMBNAIL_DIR = tempfile.mkdtemp()

                fix_video_indexes(video_uuid, "photos/device-1/20260213_photo.jpg", db_session)

            db_session.expire_all()
            job = db_session.query(VideoIndexStatus).filter(
                VideoIndexStatus.video_id == video_uuid
            ).first()

            assert job.status == "completed"
            assert job.transcript_indexed is True
            assert job.clip_indexed is True

            # Transcript and clips should NOT have been called
            mock_transcript.assert_not_called()
            mock_clips.assert_not_called()

            # Visual, captions, and faces SHOULD have been called
            mock_visual.assert_called_once()
            mock_captions.assert_called_once()
            mock_faces.assert_called_once()
        finally:
            os.unlink(tmp_path)

    def test_photo_uses_extract_photo_frame(self, db_session):
        """Photo indexing uses extract_photo_frame instead of extract_frames."""
        from indexing.pipeline import fix_video_indexes
        from models import VideoIndexStatus
        from tests.conftest import insert_video_stub

        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        db_session.add(VideoIndexStatus(
            video_id=video_uuid,
            object_name="photos/bulk/20260213_pic.png",
            status="pending",
        ))
        db_session.commit()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            Image.new("RGB", (64, 64), color="green").save(f, "PNG")
            tmp_path = f.name

        try:
            with patch("indexing.pipeline.download_video", return_value=tmp_path), \
                 patch("indexing.pipeline.extract_photo_frame", return_value=[(0, 0, Image.new("RGB", (64, 64)))]) as mock_photo, \
                 patch("indexing.pipeline.extract_frames") as mock_video_frames, \
                 patch("indexing.pipeline._store_frame_embeddings", return_value=1), \
                 patch("indexing.pipeline._store_caption_embeddings", return_value=0), \
                 patch("indexing.pipeline._store_face_detections", return_value=0), \
                 patch("indexing.pipeline.settings") as mock_settings:
                mock_settings.CAPTION_ENABLED = True
                mock_settings.CLIP_ENABLED = True
                mock_settings.FACE_CLUSTERING_ENABLED = True
                mock_settings.DEVICE = "cpu"

                fix_video_indexes(video_uuid, "photos/bulk/20260213_pic.png", db_session)

            # extract_photo_frame should have been called, not extract_frames
            mock_photo.assert_called_once()
            mock_video_frames.assert_not_called()
        finally:
            os.unlink(tmp_path)

    def test_video_still_uses_extract_frames(self, db_session):
        """Video indexing still uses extract_frames (not extract_photo_frame)."""
        from indexing.pipeline import fix_video_indexes
        from models import VideoIndexStatus
        from tests.conftest import insert_video_stub

        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        db_session.add(VideoIndexStatus(
            video_id=video_uuid,
            object_name="videos/device-1/20260213_clip.mp4",
            status="pending",
        ))
        db_session.commit()

        bright_frame = Image.new("RGB", (64, 64), color="white")

        with patch("indexing.pipeline.download_video", return_value="/fake/video.mp4"), \
             patch("indexing.pipeline.extract_photo_frame") as mock_photo, \
             patch("indexing.pipeline.extract_frames", return_value=[(0, 0, bright_frame)]) as mock_video_frames, \
             patch("indexing.pipeline._store_frame_embeddings", return_value=1), \
             patch("indexing.pipeline._store_caption_embeddings", return_value=0), \
             patch("indexing.pipeline._store_transcript_embeddings", return_value=0), \
             patch("indexing.pipeline._store_clip_embeddings", return_value=0), \
             patch("indexing.pipeline._store_face_detections", return_value=0), \
             patch("indexing.pipeline.settings") as mock_settings, \
             patch("os.path.exists", return_value=False):
            mock_settings.CAPTION_ENABLED = True
            mock_settings.CLIP_ENABLED = True
            mock_settings.FACE_CLUSTERING_ENABLED = True
            mock_settings.DEVICE = "cpu"
            mock_settings.FRAME_INTERVAL_SEC = 2.0

            fix_video_indexes(video_uuid, "videos/device-1/20260213_clip.mp4", db_session)

        # extract_frames should have been called, not extract_photo_frame
        mock_video_frames.assert_called_once()
        mock_photo.assert_not_called()
