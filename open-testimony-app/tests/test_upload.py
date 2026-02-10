"""Tests for the upload endpoint."""
import json
import hashlib

from conftest import upload_test_media


def test_upload_video(api, base_url, registered_device, signing_key, test_video_file):
    """Upload a video file and verify response."""
    device_id, public_key_pem = registered_device
    r = upload_test_media(
        api, base_url, device_id, public_key_pem, signing_key, test_video_file,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert "video_id" in data
    assert data["verification_status"] in ("verified-mvp", "error-mvp")


def test_upload_photo_source(api, base_url, registered_device, signing_key, test_video_file):
    """Upload with source='upload' and media_type='photo'."""
    device_id, public_key_pem = registered_device
    r = upload_test_media(
        api, base_url, device_id, public_key_pem, signing_key, test_video_file,
        source="upload", media_type="photo",
        exif_metadata={"camera_make": "Apple", "camera_model": "iPhone 15"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    # Imported media should get signed-upload status (MVP key format)
    assert data["verification_status"] in ("signed-upload", "error-mvp")


def test_upload_unregistered_device(api, base_url, signing_key, test_video_file):
    """Upload from an unregistered device should fail with 403."""
    with open(test_video_file, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    payload = {
        "video_hash": file_hash,
        "timestamp": "2026-02-08T12:00:00",
        "location": {"lat": 0.0, "lon": 0.0},
        "incident_tags": [],
        "source": "live",
        "media_type": "video",
    }
    metadata = {
        "version": "1.0",
        "auth": {
            "device_id": "nonexistent-device-xyz",
            "public_key_pem": "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----",
        },
        "payload": payload,
        "signature": "ZmFrZQ==",
    }
    with open(test_video_file, "rb") as f:
        r = api.post(
            f"{base_url}/upload",
            files={"video": ("test.mp4", f, "video/mp4")},
            data={"metadata": json.dumps(metadata)},
        )
    assert r.status_code == 403


def test_upload_hash_mismatch(api, base_url, registered_device, signing_key, test_video_file):
    """Upload with wrong hash should fail with 400."""
    device_id, public_key_pem = registered_device
    payload = {
        "video_hash": "0000000000000000000000000000000000000000000000000000000000000000",
        "timestamp": "2026-02-08T12:00:00",
        "location": {"lat": 0.0, "lon": 0.0},
        "incident_tags": [],
        "source": "live",
        "media_type": "video",
    }
    metadata = {
        "version": "1.0",
        "auth": {"device_id": device_id, "public_key_pem": public_key_pem},
        "payload": payload,
        "signature": "ZmFrZQ==",
    }
    with open(test_video_file, "rb") as f:
        r = api.post(
            f"{base_url}/upload",
            files={"video": ("test.mp4", f, "video/mp4")},
            data={"metadata": json.dumps(metadata)},
        )
    assert r.status_code == 400
    assert "hash mismatch" in r.json()["detail"].lower()
