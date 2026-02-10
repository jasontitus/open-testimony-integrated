"""Tests for web annotation editing, soft delete, and audit trail integration."""
import pytest
import requests

BASE_URL = __import__("os").environ.get("API_BASE_URL", "http://localhost:18080/api")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def staff_session(admin_session):
    """Ensure teststaff exists, then login as staff."""
    # Create if doesn't exist (ignore 409)
    admin_session.post(f"{BASE_URL}/auth/users", json={
        "username": "webstaff",
        "password": "staffpass",
        "display_name": "Web Staff",
        "role": "staff",
    })
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"username": "webstaff", "password": "staffpass"})
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def test_video_id(admin_session):
    """Get the first video from the list (requires at least one uploaded video)."""
    r = admin_session.get(f"{BASE_URL}/videos?limit=1")
    videos = r.json()["videos"]
    if not videos:
        pytest.skip("No videos in database to test against")
    return videos[0]["id"]


class TestWebAnnotations:
    def test_staff_can_edit_annotations(self, staff_session, test_video_id):
        r = staff_session.put(f"{BASE_URL}/videos/{test_video_id}/annotations/web", json={
            "category": "incident",
            "location_description": "Test location from web",
            "notes": "Web annotation test",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_annotations_persisted(self, admin_session, test_video_id):
        r = admin_session.get(f"{BASE_URL}/videos/{test_video_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["category"] == "incident"
        assert data["location_description"] == "Test location from web"
        assert data["notes"] == "Web annotation test"

    def test_edit_incident_tags(self, staff_session, test_video_id):
        r = staff_session.put(f"{BASE_URL}/videos/{test_video_id}/annotations/web", json={
            "incident_tags": ["web-test", "automated"],
        })
        assert r.status_code == 200

    def test_unauthenticated_cannot_edit(self, test_video_id):
        r = requests.put(f"{BASE_URL}/videos/{test_video_id}/annotations/web", json={
            "notes": "hack",
        })
        assert r.status_code == 401

    def test_web_annotation_creates_audit_entry(self, admin_session, test_video_id):
        r = admin_session.get(f"{BASE_URL}/videos/{test_video_id}/audit")
        assert r.status_code == 200
        entries = r.json()["entries"]
        web_edits = [e for e in entries if e["event_type"] == "web_annotation_update"]
        assert len(web_edits) > 0
        # Should include user info
        assert "updated_by" in web_edits[-1]["event_data"]


class TestSoftDelete:
    def test_staff_cannot_delete(self, staff_session, test_video_id):
        r = staff_session.delete(f"{BASE_URL}/videos/{test_video_id}")
        assert r.status_code == 403

    def test_admin_can_delete(self, admin_session):
        """Create a disposable video reference and delete it."""
        # Get a video to delete (use second one if available to not break other tests)
        r = admin_session.get(f"{BASE_URL}/videos?limit=10")
        videos = r.json()["videos"]
        if len(videos) < 2:
            pytest.skip("Need at least 2 videos to test delete without breaking other tests")

        target_id = videos[-1]["id"]
        r = admin_session.delete(f"{BASE_URL}/videos/{target_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "success"

        # Deleted video should not appear in list
        r = admin_session.get(f"{BASE_URL}/videos?limit=50")
        ids = [v["id"] for v in r.json()["videos"]]
        assert target_id not in ids

        # Deleted video should return 404 on detail
        r = admin_session.get(f"{BASE_URL}/videos/{target_id}")
        assert r.status_code == 404

    def test_delete_creates_audit_entry(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/audit-log?event_type=video_deleted&limit=1")
        assert r.status_code == 200
        entries = r.json()["entries"]
        assert len(entries) > 0
        assert entries[0]["event_type"] == "video_deleted"


class TestAuditChainIntegrity:
    def test_chain_still_valid(self, admin_session):
        """After all web operations, the audit chain should still verify."""
        r = admin_session.get(f"{BASE_URL}/audit-log/verify")
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True, f"Audit chain broken: {data.get('errors')}"
