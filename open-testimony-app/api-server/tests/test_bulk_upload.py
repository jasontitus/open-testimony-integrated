"""Tests for the bulk upload endpoint — admin-only multi-file upload with unverified status."""
import hashlib
import json
import os
import struct
import sys
from io import BytesIO
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Video, AuditLog


def _make_minimal_jpeg(width=1, height=1):
    """Create a minimal valid JPEG byte string (no EXIF)."""
    # Smallest valid JPEG: SOI + APP0 + minimal frame
    import struct
    buf = bytearray()
    buf += b'\xff\xd8'  # SOI
    buf += b'\xff\xe0'  # APP0
    buf += struct.pack('>H', 16)  # length
    buf += b'JFIF\x00'  # identifier
    buf += b'\x01\x01'  # version
    buf += b'\x00'      # units
    buf += struct.pack('>HH', 1, 1)  # density
    buf += b'\x00\x00'  # thumbnail
    buf += b'\xff\xd9'  # EOI
    return bytes(buf)


class TestBulkUploadAccess:
    """Verify that bulk upload requires admin authentication."""

    def test_unauthenticated_rejected(self, client):
        """Unauthenticated requests are rejected with 401."""
        resp = client.post(
            "/bulk-upload",
            files=[("files", ("test.mp4", BytesIO(b"video"), "video/mp4"))],
        )
        assert resp.status_code == 401

    def test_staff_rejected(self, app, db_session):
        """Staff users cannot use bulk upload (admin only)."""
        from auth import hash_password, create_access_token
        from models import User
        from datetime import datetime

        user = User(
            username="test-staff",
            password_hash=hash_password("testpass"),
            display_name="Staff",
            role="staff",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()

        from fastapi.testclient import TestClient
        c = TestClient(app)
        token = create_access_token({"sub": user.username})
        c.cookies.set("access_token", token)

        resp = c.post(
            "/bulk-upload",
            files=[("files", ("test.mp4", BytesIO(b"video"), "video/mp4"))],
        )
        assert resp.status_code == 403


class TestBulkUploadBasic:
    """Core bulk upload functionality."""

    def test_single_video_upload(self, admin_client, mock_minio, db_session):
        """Upload a single video file via bulk upload."""
        video_bytes = b"fake-video-content-for-bulk"

        resp = admin_client.post(
            "/bulk-upload",
            files=[("files", ("test.mp4", BytesIO(video_bytes), "video/mp4"))],
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["total"] == 1
        assert body["succeeded"] == 1
        assert body["failed"] == 0
        assert len(body["results"]) == 1

        result = body["results"][0]
        assert result["filename"] == "test.mp4"
        assert result["status"] == "success"
        assert result["verification_status"] == "unverified"
        assert result["media_type"] == "video"
        assert "video_id" in result

    def test_single_photo_upload(self, admin_client, mock_minio, db_session):
        """Upload a single photo file via bulk upload."""
        photo_bytes = _make_minimal_jpeg()

        resp = admin_client.post(
            "/bulk-upload",
            files=[("files", ("photo.jpg", BytesIO(photo_bytes), "image/jpeg"))],
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        result = body["results"][0]
        assert result["media_type"] == "photo"
        assert result["verification_status"] == "unverified"

    def test_multiple_files_upload(self, admin_client, mock_minio, db_session):
        """Upload multiple files in a single request."""
        files = [
            ("files", ("video1.mp4", BytesIO(b"video-content-1"), "video/mp4")),
            ("files", ("video2.mp4", BytesIO(b"video-content-2"), "video/mp4")),
            ("files", ("photo1.jpg", BytesIO(b"photo-content-1"), "image/jpeg")),
        ]

        resp = admin_client.post("/bulk-upload", files=files)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["succeeded"] == 3
        assert body["failed"] == 0

        # Verify media types detected correctly
        media_types = {r["filename"]: r["media_type"] for r in body["results"]}
        assert media_types["video1.mp4"] == "video"
        assert media_types["video2.mp4"] == "video"
        assert media_types["photo1.jpg"] == "photo"

    def test_empty_file_reports_error(self, admin_client, mock_minio, db_session):
        """An empty file in the batch should report an error for that file."""
        files = [
            ("files", ("empty.mp4", BytesIO(b""), "video/mp4")),
            ("files", ("good.mp4", BytesIO(b"real-content"), "video/mp4")),
        ]

        resp = admin_client.post("/bulk-upload", files=files)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "partial"
        assert body["succeeded"] == 1
        assert body["failed"] == 1

        # Identify which result is error vs success
        error_result = next(r for r in body["results"] if r["status"] == "error")
        assert error_result["filename"] == "empty.mp4"
        assert "empty" in error_result["detail"].lower()


class TestBulkUploadDatabase:
    """Verify database records created by bulk upload."""

    def test_creates_video_record(self, admin_client, mock_minio, db_session):
        """Bulk upload creates a Video row with correct fields."""
        video_bytes = b"db-check-content"

        resp = admin_client.post(
            "/bulk-upload",
            files=[("files", ("test.mp4", BytesIO(video_bytes), "video/mp4"))],
        )

        assert resp.status_code == 200
        video_id = resp.json()["results"][0]["video_id"]

        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video is not None
        assert video.verification_status == "unverified"
        assert video.source == "bulk-upload"
        assert video.device_id == "bulk-upload"
        assert video.file_hash == hashlib.sha256(video_bytes).hexdigest()
        assert video.media_type == "video"
        assert video.incident_tags == []

    def test_creates_audit_log_entry(self, admin_client, mock_minio, db_session):
        """Bulk upload creates an audit log entry for each file."""
        resp = admin_client.post(
            "/bulk-upload",
            files=[("files", ("test.mp4", BytesIO(b"audit-check"), "video/mp4"))],
        )

        assert resp.status_code == 200
        video_id = resp.json()["results"][0]["video_id"]

        entry = (
            db_session.query(AuditLog)
            .filter(AuditLog.event_type == "bulk_upload")
            .first()
        )
        assert entry is not None
        assert str(entry.video_id) == video_id
        assert entry.event_data["verification_status"] == "unverified"
        assert entry.event_data["media_type"] == "video"

    def test_photo_stored_in_photos_path(self, admin_client, mock_minio, db_session):
        """Photos are stored under photos/bulk/ in MinIO."""
        resp = admin_client.post(
            "/bulk-upload",
            files=[("files", ("img.jpg", BytesIO(b"photo-data"), "image/jpeg"))],
        )

        assert resp.status_code == 200
        video_id = resp.json()["results"][0]["video_id"]

        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video.object_name.startswith("photos/bulk/")

    def test_video_stored_in_videos_path(self, admin_client, mock_minio, db_session):
        """Videos are stored under videos/bulk/ in MinIO."""
        resp = admin_client.post(
            "/bulk-upload",
            files=[("files", ("clip.mp4", BytesIO(b"video-data"), "video/mp4"))],
        )

        assert resp.status_code == 200
        video_id = resp.json()["results"][0]["video_id"]

        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video.object_name.startswith("videos/bulk/")

    def test_metadata_json_contains_admin_info(self, admin_client, mock_minio, db_session):
        """The metadata_json should record the uploading admin and original filename."""
        resp = admin_client.post(
            "/bulk-upload",
            files=[("files", ("evidence.mp4", BytesIO(b"data"), "video/mp4"))],
        )

        assert resp.status_code == 200
        video_id = resp.json()["results"][0]["video_id"]

        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video.metadata_json["source"] == "bulk-upload"
        assert video.metadata_json["uploaded_by"] == "test-admin"
        assert video.metadata_json["original_filename"] == "evidence.mp4"


class TestBulkUploadMinIO:
    """Verify MinIO storage interactions."""

    def test_minio_called_per_file(self, admin_client, mock_minio, db_session):
        """MinIO put_object should be called once per uploaded file."""
        files = [
            ("files", ("a.mp4", BytesIO(b"aaa"), "video/mp4")),
            ("files", ("b.mp4", BytesIO(b"bbb"), "video/mp4")),
        ]

        resp = admin_client.post("/bulk-upload", files=files)
        assert resp.status_code == 200
        assert mock_minio.put_object.call_count == 2

    def test_minio_receives_correct_size(self, admin_client, mock_minio, db_session):
        """MinIO receives the correct file size."""
        content = b"precise-size-content"

        resp = admin_client.post(
            "/bulk-upload",
            files=[("files", ("test.mp4", BytesIO(content), "video/mp4"))],
        )

        assert resp.status_code == 200
        call_kwargs = mock_minio.put_object.call_args
        assert call_kwargs.kwargs["length"] == len(content)


class TestBulkUploadMediaDetection:
    """Verify media type detection from file extensions and content types."""

    def test_detects_video_extensions(self, admin_client, mock_minio, db_session):
        """Common video extensions are detected as video."""
        for ext in ["mp4", "mov", "avi", "mkv"]:
            resp = admin_client.post(
                "/bulk-upload",
                files=[("files", (f"test.{ext}", BytesIO(b"data"), f"video/{ext}"))],
            )
            assert resp.status_code == 200
            assert resp.json()["results"][0]["media_type"] == "video"

    def test_detects_photo_extensions(self, admin_client, mock_minio, db_session):
        """Common photo extensions are detected as photo."""
        for ext, ct in [("jpg", "image/jpeg"), ("png", "image/png"), ("heic", "image/heic")]:
            resp = admin_client.post(
                "/bulk-upload",
                files=[("files", (f"test.{ext}", BytesIO(b"data"), ct))],
            )
            assert resp.status_code == 200
            assert resp.json()["results"][0]["media_type"] == "photo"
