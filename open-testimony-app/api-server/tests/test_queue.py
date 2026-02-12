"""Tests for queue management endpoints (GET /queue, GET /queue/stats, PUT /videos/{id}/review)."""
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import hash_password, create_access_token
from models import User, Video

from fastapi.testclient import TestClient


def _make_staff_client(app, db_session):
    """Create a staff-level TestClient."""
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
    db_session.refresh(user)

    c = TestClient(app)
    token = create_access_token({"sub": user.username})
    c.cookies.set("access_token", token)
    return c, user


def _insert_video(db_session, review_status="pending", source="live", category=None,
                  tags=None, notes=None, location_description=None):
    """Insert a test video and return its ID."""
    v = Video(
        id=uuid.uuid4(),
        device_id="test-device",
        object_name=f"videos/test/{uuid.uuid4()}.mp4",
        file_hash="a" * 64,
        timestamp=datetime.utcnow(),
        latitude=40.7128,
        longitude=-74.006,
        verification_status="verified",
        metadata_json={},
        uploaded_at=datetime.utcnow(),
        source=source,
        review_status=review_status,
        incident_tags=tags or [],
        category=category,
        notes=notes,
        location_description=location_description,
    )
    db_session.add(v)
    db_session.commit()
    return str(v.id)


class TestGetQueue:
    """GET /queue — staff-only queue listing with filters."""

    def test_requires_auth(self, client):
        """Unauthenticated users get 401."""
        resp = client.get("/queue")
        assert resp.status_code == 401

    def test_requires_staff(self, app, db_session):
        """Non-staff users cannot access the queue."""
        # A regular device-registered user without a role should get 401
        resp = TestClient(app).get("/queue")
        assert resp.status_code == 401

    def test_returns_pending_by_default(self, app, db_session):
        """GET /queue returns only pending videos by default."""
        staff_client, _ = _make_staff_client(app, db_session)

        _insert_video(db_session, review_status="pending")
        _insert_video(db_session, review_status="reviewed")
        _insert_video(db_session, review_status="flagged")

        resp = staff_client.get("/queue")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["count"] == 1
        assert all(v["review_status"] == "pending" for v in body["videos"])

    def test_filter_by_review_status(self, app, db_session):
        """GET /queue?review_status=reviewed returns only reviewed videos."""
        staff_client, _ = _make_staff_client(app, db_session)

        _insert_video(db_session, review_status="pending")
        _insert_video(db_session, review_status="reviewed")

        resp = staff_client.get("/queue", params={"review_status": "reviewed"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["videos"][0]["review_status"] == "reviewed"

    def test_filter_by_category(self, app, db_session):
        """GET /queue?category=interview filters by category."""
        staff_client, _ = _make_staff_client(app, db_session)

        _insert_video(db_session, category="interview")
        _insert_video(db_session, category="incident")

        resp = staff_client.get("/queue", params={"review_status": "", "category": "interview"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["videos"][0]["category"] == "interview"

    def test_filter_by_source(self, app, db_session):
        """GET /queue?source=upload filters by source."""
        staff_client, _ = _make_staff_client(app, db_session)

        _insert_video(db_session, source="live")
        _insert_video(db_session, source="upload")

        resp = staff_client.get("/queue", params={"review_status": "", "source": "upload"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["videos"][0]["source"] == "upload"

    def test_search_filter(self, app, db_session):
        """GET /queue?search=... searches notes and location_description."""
        staff_client, _ = _make_staff_client(app, db_session)

        _insert_video(db_session, notes="Incident near the courthouse")
        _insert_video(db_session, notes="Nothing relevant")

        resp = staff_client.get("/queue", params={"review_status": "", "search": "courthouse"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert "courthouse" in body["videos"][0]["notes"]

    def test_sort_newest(self, app, db_session):
        """GET /queue?sort=newest returns most recent first."""
        staff_client, _ = _make_staff_client(app, db_session)

        vid1 = _insert_video(db_session)
        vid2 = _insert_video(db_session)

        resp = staff_client.get("/queue", params={"sort": "newest"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["videos"]) == 2
        # Most recent (vid2) should be first
        assert body["videos"][0]["id"] == vid2

    def test_pagination(self, app, db_session):
        """GET /queue supports limit and offset."""
        staff_client, _ = _make_staff_client(app, db_session)

        for _ in range(5):
            _insert_video(db_session)

        resp = staff_client.get("/queue", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert body["count"] == 2

        resp2 = staff_client.get("/queue", params={"limit": 2, "offset": 2})
        body2 = resp2.json()
        assert body2["count"] == 2
        # Different videos
        assert body["videos"][0]["id"] != body2["videos"][0]["id"]

    def test_response_fields(self, app, db_session):
        """Queue items include all expected fields."""
        staff_client, _ = _make_staff_client(app, db_session)
        _insert_video(db_session, category="incident", tags=["arrest"])

        resp = staff_client.get("/queue")
        assert resp.status_code == 200
        video = resp.json()["videos"][0]
        expected_fields = [
            "id", "device_id", "timestamp", "incident_tags", "source",
            "media_type", "category", "verification_status", "review_status",
            "uploaded_at",
        ]
        for field in expected_fields:
            assert field in video, f"Missing field: {field}"


class TestQueueStats:
    """GET /queue/stats — counts by review status."""

    def test_requires_auth(self, client):
        resp = client.get("/queue/stats")
        assert resp.status_code == 401

    def test_returns_counts(self, app, db_session):
        """Stats endpoint returns counts broken down by status."""
        staff_client, _ = _make_staff_client(app, db_session)

        _insert_video(db_session, review_status="pending")
        _insert_video(db_session, review_status="pending")
        _insert_video(db_session, review_status="reviewed")
        _insert_video(db_session, review_status="flagged")

        resp = staff_client.get("/queue/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["pending"] == 2
        assert stats["reviewed"] == 1
        assert stats["flagged"] == 1
        assert stats["total"] == 4

    def test_empty_stats(self, app, db_session):
        """Stats with no videos returns all zeros."""
        staff_client, _ = _make_staff_client(app, db_session)

        resp = staff_client.get("/queue/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["pending"] == 0
        assert stats["reviewed"] == 0
        assert stats["flagged"] == 0
        assert stats["total"] == 0


class TestUpdateReviewStatus:
    """PUT /videos/{id}/review — mark video as reviewed/flagged/pending."""

    def test_requires_auth(self, client):
        resp = client.put(f"/videos/{uuid.uuid4()}/review", json={"review_status": "reviewed"})
        assert resp.status_code == 401

    def test_mark_as_reviewed(self, app, db_session):
        """Marking a video as reviewed sets reviewed_by and reviewed_at."""
        staff_client, user = _make_staff_client(app, db_session)
        vid = _insert_video(db_session, review_status="pending")

        resp = staff_client.put(f"/videos/{vid}/review", json={"review_status": "reviewed"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["review_status"] == "reviewed"
        assert body["reviewed_by"] == user.username

    def test_mark_as_flagged(self, app, db_session):
        """Marking a video as flagged works."""
        staff_client, _ = _make_staff_client(app, db_session)
        vid = _insert_video(db_session)

        resp = staff_client.put(f"/videos/{vid}/review", json={"review_status": "flagged"})
        assert resp.status_code == 200
        assert resp.json()["review_status"] == "flagged"

    def test_reset_to_pending(self, app, db_session):
        """Resetting to pending clears reviewed_by and reviewed_at."""
        staff_client, _ = _make_staff_client(app, db_session)
        vid = _insert_video(db_session, review_status="reviewed")

        resp = staff_client.put(f"/videos/{vid}/review", json={"review_status": "pending"})
        assert resp.status_code == 200
        assert resp.json()["review_status"] == "pending"

        # Verify cleared in queue listing
        resp2 = staff_client.get("/queue", params={"review_status": "pending"})
        video = [v for v in resp2.json()["videos"] if v["id"] == vid][0]
        assert video["reviewed_at"] is None
        assert video["reviewed_by"] is None

    def test_invalid_status_rejected(self, app, db_session):
        """Invalid review_status values are rejected with 400."""
        staff_client, _ = _make_staff_client(app, db_session)
        vid = _insert_video(db_session)

        resp = staff_client.put(f"/videos/{vid}/review", json={"review_status": "invalid"})
        assert resp.status_code == 400

    def test_nonexistent_video_404(self, app, db_session):
        """Reviewing a nonexistent video returns 404."""
        staff_client, _ = _make_staff_client(app, db_session)

        resp = staff_client.put(
            f"/videos/{uuid.uuid4()}/review",
            json={"review_status": "reviewed"},
        )
        assert resp.status_code == 404

    def test_creates_audit_entry(self, app, db_session):
        """Review status change creates an audit log entry."""
        staff_client, _ = _make_staff_client(app, db_session)
        vid = _insert_video(db_session)

        staff_client.put(f"/videos/{vid}/review", json={"review_status": "reviewed"})

        # Check audit log
        resp = staff_client.get(f"/videos/{vid}/audit")
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        review_entries = [e for e in entries if e["event_type"] == "queue_review"]
        assert len(review_entries) == 1
        assert review_entries[0]["event_data"]["new_status"] == "reviewed"
        assert review_entries[0]["event_data"]["old_status"] == "pending"


class TestCategoryCounts:
    """GET /categories/counts — category usage breakdown."""

    def test_returns_counts(self, app, db_session):
        """Returns categories sorted by count."""
        staff_client, _ = _make_staff_client(app, db_session)

        _insert_video(db_session, category="incident")
        _insert_video(db_session, category="incident")
        _insert_video(db_session, category="interview")

        resp = staff_client.get("/categories/counts")
        assert resp.status_code == 200
        cats = resp.json()["categories"]
        assert len(cats) == 2
        # incident has more, should be first
        assert cats[0]["category"] == "incident"
        assert cats[0]["count"] == 2
        assert cats[1]["category"] == "interview"
        assert cats[1]["count"] == 1

    def test_excludes_null_category(self, app, db_session):
        """Videos without a category are excluded."""
        staff_client, _ = _make_staff_client(app, db_session)

        _insert_video(db_session, category=None)
        _insert_video(db_session, category="incident")

        resp = staff_client.get("/categories/counts")
        cats = resp.json()["categories"]
        assert len(cats) == 1
        assert cats[0]["category"] == "incident"

    def test_empty_returns_empty(self, client):
        """No videos returns empty categories list."""
        resp = client.get("/categories/counts")
        assert resp.status_code == 200
        assert resp.json()["categories"] == []
