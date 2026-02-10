"""Tests for the audit log endpoints."""
from conftest import upload_test_media


def test_audit_log_list(api, base_url):
    """Audit log should return entries."""
    r = api.get(f"{base_url}/audit-log")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "entries" in data
    assert isinstance(data["entries"], list)


def test_audit_log_has_required_fields(api, base_url):
    """Each audit entry should have all required fields."""
    r = api.get(f"{base_url}/audit-log", params={"limit": 1})
    entries = r.json()["entries"]
    if entries:
        entry = entries[0]
        for field in (
            "id", "sequence_number", "event_type", "event_data",
            "entry_hash", "previous_hash", "created_at",
        ):
            assert field in entry, f"Missing field: {field}"


def test_audit_log_filter_by_event_type(api, base_url, registered_device):
    """Filter audit log by event_type."""
    r = api.get(f"{base_url}/audit-log", params={"event_type": "device_register"})
    assert r.status_code == 200
    for entry in r.json()["entries"]:
        assert entry["event_type"] == "device_register"


def test_audit_log_verify_chain(api, base_url):
    """Chain verification should pass."""
    r = api.get(f"{base_url}/audit-log/verify")
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert data["entries_checked"] > 0
    assert data["errors"] == []


def test_video_audit_trail(
    api, base_url, registered_device, signing_key, test_video_file
):
    """Upload a video, annotate it, then check its audit trail."""
    device_id, public_key_pem = registered_device
    upload_r = upload_test_media(
        api, base_url, device_id, public_key_pem, signing_key, test_video_file,
    )
    video_id = upload_r.json()["video_id"]

    # Annotate it
    api.put(
        f"{base_url}/videos/{video_id}/annotations",
        json={
            "device_id": device_id,
            "category": "interview",
            "notes": "audit trail test",
        },
    )

    # Check audit trail
    r = api.get(f"{base_url}/videos/{video_id}/audit")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) >= 2  # upload + annotation_update

    event_types = [e["event_type"] for e in entries]
    assert "upload" in event_types
    assert "annotation_update" in event_types

    # Entries should be in sequence order
    seq_numbers = [e["sequence_number"] for e in entries]
    assert seq_numbers == sorted(seq_numbers)


def test_audit_log_pagination(api, base_url):
    r = api.get(f"{base_url}/audit-log", params={"limit": 2, "offset": 0})
    assert r.status_code == 200
    assert len(r.json()["entries"]) <= 2


def test_verify_chain_still_valid_after_operations(
    api, base_url, registered_device, signing_key, test_video_file
):
    """After upload + annotation, chain should still verify."""
    device_id, public_key_pem = registered_device
    upload_r = upload_test_media(
        api, base_url, device_id, public_key_pem, signing_key, test_video_file,
    )
    video_id = upload_r.json()["video_id"]
    api.put(
        f"{base_url}/videos/{video_id}/annotations",
        json={"device_id": device_id, "category": "incident"},
    )

    r = api.get(f"{base_url}/audit-log/verify")
    assert r.status_code == 200
    assert r.json()["valid"] is True
