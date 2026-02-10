"""Tests for the tags system: GET /tags, device tag updates, admin tag deletion, and autocomplete flow."""
import pytest
import requests

from conftest import upload_test_media

BASE_URL = __import__("os").environ.get("API_BASE_URL", "http://localhost:18080/api")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def staff_session(admin_session):
    admin_session.post(f"{BASE_URL}/auth/users", json={
        "username": "tagstaff",
        "password": "staffpass",
        "display_name": "Tag Staff",
        "role": "staff",
    })
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"username": "tagstaff", "password": "staffpass"})
    assert r.status_code == 200
    return s


class TestGetTags:
    """GET /tags returns default tags and merges user-created tags."""

    def test_get_tags_returns_defaults(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/tags")
        assert r.status_code == 200
        data = r.json()
        assert "default_tags" in data
        assert "all_tags" in data
        assert len(data["default_tags"]) > 0
        assert "protest" in data["default_tags"]
        assert "police-violence" in data["default_tags"]
        assert "arrest" in data["default_tags"]

    def test_get_tags_unauthenticated(self):
        """Tags endpoint should work without authentication (mobile devices need it)."""
        r = requests.get(f"{BASE_URL}/tags")
        assert r.status_code == 200
        assert "all_tags" in r.json()

    def test_all_tags_includes_defaults(self):
        r = requests.get(f"{BASE_URL}/tags")
        data = r.json()
        for tag in data["default_tags"]:
            assert tag in data["all_tags"]


class TestDeviceAnnotationTags:
    """Device PUT /videos/{id}/annotations now accepts incident_tags."""

    def test_device_can_add_tags(
        self, api, base_url, registered_device, signing_key, test_video_file
    ):
        device_id, public_key_pem = registered_device
        resp = upload_test_media(
            api, base_url, device_id, public_key_pem, signing_key, test_video_file,
        )
        assert resp.status_code == 200
        video_id = resp.json()["video_id"]

        r = api.put(
            f"{base_url}/videos/{video_id}/annotations",
            json={
                "device_id": device_id,
                "category": "incident",
                "incident_tags": ["protest", "tear-gas", "my-custom-tag"],
            },
        )
        assert r.status_code == 200

        detail = api.get(f"{base_url}/videos/{video_id}").json()
        assert "protest" in detail["incident_tags"]
        assert "tear-gas" in detail["incident_tags"]
        assert "my-custom-tag" in detail["incident_tags"]

    def test_device_tags_appear_in_autocomplete(
        self, api, base_url, registered_device, signing_key, test_video_file
    ):
        """After a device adds a custom tag, it should show up in GET /tags."""
        device_id, public_key_pem = registered_device
        resp = upload_test_media(
            api, base_url, device_id, public_key_pem, signing_key, test_video_file,
        )
        assert resp.status_code == 200
        video_id = resp.json()["video_id"]

        unique_tag = "pytest-unique-tag-12345"
        api.put(
            f"{base_url}/videos/{video_id}/annotations",
            json={
                "device_id": device_id,
                "incident_tags": [unique_tag],
            },
        )

        r = requests.get(f"{base_url}/tags")
        assert r.status_code == 200
        assert unique_tag in r.json()["all_tags"]

    def test_expanded_categories_accepted(
        self, api, base_url, registered_device, signing_key, test_video_file
    ):
        """Device can now set category to 'documentation' and 'other'."""
        device_id, public_key_pem = registered_device
        resp = upload_test_media(
            api, base_url, device_id, public_key_pem, signing_key, test_video_file,
        )
        assert resp.status_code == 200
        video_id = resp.json()["video_id"]

        for cat in ["documentation", "other"]:
            r = api.put(
                f"{base_url}/videos/{video_id}/annotations",
                json={"device_id": device_id, "category": cat},
            )
            assert r.status_code == 200
            detail = api.get(f"{base_url}/videos/{video_id}").json()
            assert detail["category"] == cat


class TestWebTagUpdate:
    """Staff can update tags via web endpoint and they appear in autocomplete."""

    def test_web_tags_appear_in_autocomplete(self, staff_session, admin_session):
        r = admin_session.get(f"{BASE_URL}/videos?limit=1")
        videos = r.json()["videos"]
        if not videos:
            pytest.skip("No videos in database")
        video_id = videos[0]["id"]

        unique_web_tag = "web-unique-tag-67890"
        r = staff_session.put(f"{BASE_URL}/videos/{video_id}/annotations/web", json={
            "incident_tags": [unique_web_tag, "protest"],
        })
        assert r.status_code == 200

        r = requests.get(f"{BASE_URL}/tags")
        assert unique_web_tag in r.json()["all_tags"]


class TestAdminTagDeletion:
    """Admin can delete tags from all videos."""

    def test_admin_can_delete_tag(self, admin_session, staff_session):
        # First, add a unique tag to a video
        r = admin_session.get(f"{BASE_URL}/videos?limit=1")
        videos = r.json()["videos"]
        if not videos:
            pytest.skip("No videos in database")
        video_id = videos[0]["id"]

        tag_to_delete = "delete-me-test-tag"
        staff_session.put(f"{BASE_URL}/videos/{video_id}/annotations/web", json={
            "incident_tags": [tag_to_delete, "protest"],
        })

        # Verify it exists
        detail = admin_session.get(f"{BASE_URL}/videos/{video_id}").json()
        assert tag_to_delete in detail["incident_tags"]

        # Delete it
        r = admin_session.delete(f"{BASE_URL}/tags", json={"tag": tag_to_delete})
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        assert r.json()["videos_affected"] >= 1

        # Verify it's gone from the video
        detail = admin_session.get(f"{BASE_URL}/videos/{video_id}").json()
        assert tag_to_delete not in detail["incident_tags"]
        # Other tags should still be there
        assert "protest" in detail["incident_tags"]

    def test_staff_cannot_delete_tags(self, staff_session):
        r = staff_session.delete(f"{BASE_URL}/tags", json={"tag": "protest"})
        assert r.status_code == 403

    def test_delete_nonexistent_tag(self, admin_session):
        r = admin_session.delete(f"{BASE_URL}/tags", json={"tag": "never-existed-xyz"})
        assert r.status_code == 200
        assert r.json()["videos_affected"] == 0

    def test_tag_deletion_audited(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/audit-log?event_type=tag_deleted&limit=1")
        assert r.status_code == 200
        entries = r.json()["entries"]
        assert len(entries) > 0
        assert entries[0]["event_type"] == "tag_deleted"
