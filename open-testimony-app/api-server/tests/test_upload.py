"""Tests for the upload endpoint — verifies hash checking, DB records, MinIO storage."""
import hashlib
import json
import os
import sys
from io import BytesIO
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import make_upload_payload


class TestUploadBasic:
    """Core upload functionality that must survive refactoring."""

    def test_upload_success(self, client, registered_device, mock_minio):
        """Upload with valid hash and registered device succeeds."""
        video_bytes = b"fake-video-content-12345"
        metadata, _ = make_upload_payload(video_bytes, registered_device)

        resp = client.post(
            "/upload",
            files={"video": ("test.mp4", BytesIO(video_bytes), "video/mp4")},
            data={"metadata": json.dumps(metadata)},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["verification_status"] == "verified-mvp"
        assert "video_id" in body

        # MinIO put_object should have been called once
        mock_minio.put_object.assert_called_once()

    def test_upload_hash_mismatch(self, client, registered_device):
        """Upload with wrong hash is rejected with 400."""
        video_bytes = b"real-content"
        metadata, _ = make_upload_payload(video_bytes, registered_device)
        # Corrupt the hash
        metadata["payload"]["video_hash"] = "0" * 64

        resp = client.post(
            "/upload",
            files={"video": ("test.mp4", BytesIO(video_bytes), "video/mp4")},
            data={"metadata": json.dumps(metadata)},
        )

        assert resp.status_code == 400
        assert "hash mismatch" in resp.json()["detail"].lower()

    def test_upload_unregistered_device(self, client):
        """Upload from an unregistered device is rejected with 403."""
        video_bytes = b"some-video"
        metadata, _ = make_upload_payload(video_bytes, "unknown-device-999")

        resp = client.post(
            "/upload",
            files={"video": ("test.mp4", BytesIO(video_bytes), "video/mp4")},
            data={"metadata": json.dumps(metadata)},
        )

        assert resp.status_code == 403

    def test_upload_creates_db_record(self, client, registered_device, db_session):
        """Upload creates a Video row in the database with correct fields."""
        video_bytes = b"video-for-db-check"
        metadata, _ = make_upload_payload(video_bytes, registered_device)

        resp = client.post(
            "/upload",
            files={"video": ("test.mp4", BytesIO(video_bytes), "video/mp4")},
            data={"metadata": json.dumps(metadata)},
        )

        assert resp.status_code == 200
        video_id = resp.json()["video_id"]

        from models import Video
        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video is not None
        assert video.file_hash == hashlib.sha256(video_bytes).hexdigest()
        assert video.device_id == registered_device

    def test_upload_stores_correct_size_in_minio(
        self, client, registered_device, mock_minio
    ):
        """MinIO put_object is called with correct file size and object path."""
        video_bytes = b"check-minio-content"
        metadata, _ = make_upload_payload(video_bytes, registered_device)

        resp = client.post(
            "/upload",
            files={"video": ("test.mp4", BytesIO(video_bytes), "video/mp4")},
            data={"metadata": json.dumps(metadata)},
        )

        assert resp.status_code == 200
        call_kwargs = mock_minio.put_object.call_args
        assert call_kwargs.kwargs["length"] == len(video_bytes)
        assert "videos/" in call_kwargs.kwargs["object_name"]
        assert "test-device-001" in call_kwargs.kwargs["object_name"]

    def test_upload_photo_type(self, client, registered_device, mock_minio):
        """Upload with media_type=photo stores in photos/ path."""
        video_bytes = b"fake-photo-jpeg"
        metadata, _ = make_upload_payload(video_bytes, registered_device)
        metadata["payload"]["media_type"] = "photo"

        resp = client.post(
            "/upload",
            files={"video": ("test.jpg", BytesIO(video_bytes), "image/jpeg")},
            data={"metadata": json.dumps(metadata)},
        )

        assert resp.status_code == 200
        call_kwargs = mock_minio.put_object.call_args
        object_name = call_kwargs.kwargs.get("object_name") or call_kwargs[0][1]
        assert "photos/" in object_name
