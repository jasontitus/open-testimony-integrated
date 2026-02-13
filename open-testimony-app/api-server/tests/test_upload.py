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


class TestPhotoExifExtraction:
    """EXIF time and location are extracted from photos during upload."""

    def _exif_result(self, lat=None, lon=None, datetime_str=None, raw=None):
        """Build a mock _extract_exif return value."""
        return {
            "lat": lat,
            "lon": lon,
            "datetime": datetime_str,
            "raw": raw or ({"DateTime": datetime_str} if datetime_str else None),
        }

    def test_photo_exif_overrides_location(self, client, registered_device, mock_minio, db_session):
        """Photo upload uses EXIF GPS coordinates for the DB record."""
        photo_bytes = b"fake-photo-with-gps"
        metadata, _ = make_upload_payload(photo_bytes, registered_device)
        metadata["payload"]["media_type"] = "photo"
        # Device payload has NYC coords — EXIF has Paris coords
        metadata["payload"]["location"] = {"lat": 40.7128, "lon": -74.0060}

        exif = self._exif_result(lat=48.8566, lon=2.3522)
        with patch("main._extract_exif", return_value=exif):
            resp = client.post(
                "/upload",
                files={"video": ("paris.jpg", BytesIO(photo_bytes), "image/jpeg")},
                data={"metadata": json.dumps(metadata)},
            )

        assert resp.status_code == 200
        video_id = resp.json()["video_id"]

        from models import Video
        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video is not None
        # EXIF Paris coords should override device NYC coords
        assert abs(video.latitude - 48.8566) < 0.01
        assert abs(video.longitude - 2.3522) < 0.01

    def test_photo_exif_overrides_timestamp(self, client, registered_device, mock_minio, db_session):
        """Photo upload uses EXIF DateTime for the DB record timestamp."""
        photo_bytes = b"fake-photo-with-datetime"
        metadata, _ = make_upload_payload(photo_bytes, registered_device)
        metadata["payload"]["media_type"] = "photo"

        exif = self._exif_result(datetime_str="2025:06:15 10:30:00")
        with patch("main._extract_exif", return_value=exif):
            resp = client.post(
                "/upload",
                files={"video": ("dated.jpg", BytesIO(photo_bytes), "image/jpeg")},
                data={"metadata": json.dumps(metadata)},
            )

        assert resp.status_code == 200
        video_id = resp.json()["video_id"]

        from models import Video
        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video is not None
        assert video.timestamp.year == 2025
        assert video.timestamp.month == 6
        assert video.timestamp.day == 15

    def test_photo_exif_metadata_stored(self, client, registered_device, mock_minio, db_session):
        """Photo upload stores extracted EXIF raw metadata in exif_metadata field."""
        photo_bytes = b"fake-photo-with-exif"
        metadata, _ = make_upload_payload(photo_bytes, registered_device)
        metadata["payload"]["media_type"] = "photo"

        raw_exif = {"DateTime": "2025:06:15 10:30:00", "Make": "TestCamera", "Model": "X100"}
        exif = self._exif_result(datetime_str="2025:06:15 10:30:00", raw=raw_exif)
        with patch("main._extract_exif", return_value=exif):
            resp = client.post(
                "/upload",
                files={"video": ("exif.jpg", BytesIO(photo_bytes), "image/jpeg")},
                data={"metadata": json.dumps(metadata)},
            )

        assert resp.status_code == 200
        video_id = resp.json()["video_id"]

        from models import Video
        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video is not None
        assert video.exif_metadata is not None
        assert video.exif_metadata["DateTime"] == "2025:06:15 10:30:00"
        assert video.exif_metadata["Make"] == "TestCamera"

    def test_video_upload_does_not_extract_exif(self, client, registered_device, mock_minio, db_session):
        """Video uploads still use device payload, not EXIF extraction."""
        video_bytes = b"fake-video-not-a-jpeg"
        metadata, _ = make_upload_payload(video_bytes, registered_device)
        metadata["payload"]["location"] = {"lat": 40.7128, "lon": -74.0060}

        with patch("main._extract_exif") as mock_exif:
            resp = client.post(
                "/upload",
                files={"video": ("clip.mp4", BytesIO(video_bytes), "video/mp4")},
                data={"metadata": json.dumps(metadata)},
            )

        assert resp.status_code == 200
        # _extract_exif should NOT have been called for video uploads
        mock_exif.assert_not_called()

        video_id = resp.json()["video_id"]
        from models import Video
        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video is not None
        assert abs(video.latitude - 40.7128) < 0.01
        assert abs(video.longitude - (-74.0060)) < 0.01

    def test_photo_without_exif_uses_payload(self, client, registered_device, mock_minio, db_session):
        """Photo without EXIF data falls back to device payload values."""
        photo_bytes = b"plain-jpeg-no-exif"
        metadata, _ = make_upload_payload(photo_bytes, registered_device)
        metadata["payload"]["media_type"] = "photo"
        metadata["payload"]["location"] = {"lat": 51.5074, "lon": -0.1278}

        # EXIF extraction returns empty (no GPS, no datetime)
        exif = self._exif_result()
        with patch("main._extract_exif", return_value=exif):
            resp = client.post(
                "/upload",
                files={"video": ("noexif.jpg", BytesIO(photo_bytes), "image/jpeg")},
                data={"metadata": json.dumps(metadata)},
            )

        assert resp.status_code == 200
        video_id = resp.json()["video_id"]

        from models import Video
        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video is not None
        # Should fall back to device payload London coords
        assert abs(video.latitude - 51.5074) < 0.01
        assert abs(video.longitude - (-0.1278)) < 0.01

    def test_photo_exif_partial_gps(self, client, registered_device, mock_minio, db_session):
        """EXIF with only lat (no lon) uses EXIF lat and payload lon."""
        photo_bytes = b"partial-gps-photo"
        metadata, _ = make_upload_payload(photo_bytes, registered_device)
        metadata["payload"]["media_type"] = "photo"
        metadata["payload"]["location"] = {"lat": 40.7128, "lon": -74.0060}

        exif = self._exif_result(lat=35.6762, lon=None)
        with patch("main._extract_exif", return_value=exif):
            resp = client.post(
                "/upload",
                files={"video": ("partial.jpg", BytesIO(photo_bytes), "image/jpeg")},
                data={"metadata": json.dumps(metadata)},
            )

        assert resp.status_code == 200
        video_id = resp.json()["video_id"]

        from models import Video
        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video is not None
        # Lat from EXIF, lon from device payload
        assert abs(video.latitude - 35.6762) < 0.01
        assert abs(video.longitude - (-74.0060)) < 0.01
