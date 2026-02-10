"""Tests for bridge JWT authentication."""
import os
import sys
from datetime import datetime, timedelta

from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


class TestBridgeAuth:
    """JWT validation must match Open Testimony's auth."""

    def test_valid_token_accepted(self, client, auth_cookie):
        """A valid JWT cookie grants access to protected endpoints."""
        resp = client.get("/indexing/status", cookies=auth_cookie)
        assert resp.status_code == 200

    def test_missing_token_rejected(self, client):
        """Requests without a JWT cookie get 401."""
        resp = client.get("/indexing/status")
        assert resp.status_code == 401
        assert "not authenticated" in resp.json()["detail"].lower()

    def test_invalid_token_rejected(self, client):
        """A malformed JWT gets 401."""
        resp = client.get(
            "/indexing/status", cookies={"access_token": "not-a-jwt"}
        )
        assert resp.status_code == 401

    def test_wrong_secret_rejected(self, client):
        """A JWT signed with a different secret gets 401."""
        token = jwt.encode(
            {"sub": "user", "exp": datetime(2099, 1, 1)},
            "wrong-secret-key",
            algorithm="HS256",
        )
        resp = client.get(
            "/indexing/status", cookies={"access_token": token}
        )
        assert resp.status_code == 401

    def test_expired_token_rejected(self, client):
        """An expired JWT gets 401."""
        token = jwt.encode(
            {"sub": "user", "exp": datetime(2020, 1, 1)},
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        resp = client.get(
            "/indexing/status", cookies={"access_token": token}
        )
        assert resp.status_code == 401

    def test_token_without_sub_rejected(self, client):
        """A JWT without a 'sub' claim gets 401."""
        token = jwt.encode(
            {"exp": datetime(2099, 1, 1)},
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        resp = client.get(
            "/indexing/status", cookies={"access_token": token}
        )
        assert resp.status_code == 401

    def test_webhook_does_not_require_auth(self, client, db_session):
        """The video-uploaded webhook is not auth-protected (internal service call)."""
        from tests.conftest import insert_video_stub

        vid = insert_video_stub(db_session)
        resp = client.post(
            "/hooks/video-uploaded",
            json={"video_id": vid, "object_name": "videos/test/test.mp4"},
        )
        # Should succeed without auth cookie
        assert resp.status_code == 200
