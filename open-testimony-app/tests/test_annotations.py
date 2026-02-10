"""Tests for the annotations (PUT) endpoint."""
from conftest import upload_test_media


def _create_video(api, base_url, registered_device, signing_key, test_video_file):
    """Helper: upload a video and return (video_id, device_id)."""
    device_id, public_key_pem = registered_device
    r = upload_test_media(
        api, base_url, device_id, public_key_pem, signing_key, test_video_file,
    )
    assert r.status_code == 200
    return r.json()["video_id"], device_id


def test_update_annotations(
    api, base_url, registered_device, signing_key, test_video_file
):
    video_id, device_id = _create_video(
        api, base_url, registered_device, signing_key, test_video_file
    )
    r = api.put(
        f"{base_url}/videos/{video_id}/annotations",
        json={
            "device_id": device_id,
            "category": "incident",
            "location_description": "Main St & 5th Ave",
            "notes": "Test notes from pytest",
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "success"

    # Verify saved
    detail = api.get(f"{base_url}/videos/{video_id}").json()
    assert detail["category"] == "incident"
    assert detail["location_description"] == "Main St & 5th Ave"
    assert detail["notes"] == "Test notes from pytest"
    assert detail["annotations_updated_at"] is not None


def test_update_annotations_interview_category(
    api, base_url, registered_device, signing_key, test_video_file
):
    video_id, device_id = _create_video(
        api, base_url, registered_device, signing_key, test_video_file
    )
    r = api.put(
        f"{base_url}/videos/{video_id}/annotations",
        json={"device_id": device_id, "category": "interview"},
    )
    assert r.status_code == 200
    detail = api.get(f"{base_url}/videos/{video_id}").json()
    assert detail["category"] == "interview"


def test_update_annotations_clear_category(
    api, base_url, registered_device, signing_key, test_video_file
):
    """Setting category to empty string should clear it."""
    video_id, device_id = _create_video(
        api, base_url, registered_device, signing_key, test_video_file
    )
    # Set category first
    api.put(
        f"{base_url}/videos/{video_id}/annotations",
        json={"device_id": device_id, "category": "incident"},
    )
    # Clear it
    r = api.put(
        f"{base_url}/videos/{video_id}/annotations",
        json={"device_id": device_id, "category": ""},
    )
    assert r.status_code == 200
    detail = api.get(f"{base_url}/videos/{video_id}").json()
    assert detail["category"] is None


def test_update_annotations_wrong_device(
    api, base_url, registered_device, signing_key, test_video_file
):
    """Only the owning device can update annotations."""
    video_id, _ = _create_video(
        api, base_url, registered_device, signing_key, test_video_file
    )
    r = api.put(
        f"{base_url}/videos/{video_id}/annotations",
        json={"device_id": "wrong-device-id", "category": "incident"},
    )
    assert r.status_code == 403


def test_update_annotations_invalid_category(
    api, base_url, registered_device, signing_key, test_video_file
):
    """Invalid category should return 400."""
    video_id, device_id = _create_video(
        api, base_url, registered_device, signing_key, test_video_file
    )
    r = api.put(
        f"{base_url}/videos/{video_id}/annotations",
        json={"device_id": device_id, "category": "bogus"},
    )
    assert r.status_code == 400


def test_update_annotations_nonexistent_video(api, base_url, registered_device):
    device_id, _ = registered_device
    r = api.put(
        f"{base_url}/videos/00000000-0000-0000-0000-000000000000/annotations",
        json={"device_id": device_id, "category": "incident"},
    )
    assert r.status_code == 404
