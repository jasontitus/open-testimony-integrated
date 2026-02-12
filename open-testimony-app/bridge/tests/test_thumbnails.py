"""Tests for the thumbnail serving endpoint."""
import os


class TestThumbnailEndpoint:
    def test_exact_thumbnail_found(self, client, auth_cookie, tmp_path):
        """GET /thumbnails/{id}/{ts}.jpg returns 200 when file exists."""
        import tempfile
        from unittest.mock import patch

        video_id = "test-thumb-video"
        thumb_dir = tmp_path / "thumbnails" / video_id
        thumb_dir.mkdir(parents=True)
        thumb_path = thumb_dir / "5000.jpg"
        thumb_path.write_bytes(b"\xff\xd8\xff\xe0JFIF" + b"\x00" * 100)

        # Patch settings.THUMBNAIL_DIR so the endpoint looks in our temp dir
        with patch("main.settings.THUMBNAIL_DIR", str(tmp_path / "thumbnails")):
            r = client.get(
                f"/thumbnails/{video_id}/5000.jpg",
                cookies=auth_cookie,
            )
            assert r.status_code == 200
            assert r.headers["content-type"] == "image/jpeg"

    def test_thumbnail_not_found(self, client, auth_cookie):
        """GET /thumbnails/{id}/{ts}.jpg returns 404 when missing."""
        r = client.get(
            "/thumbnails/nonexistent-video/99999.jpg",
            cookies=auth_cookie,
        )
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_thumbnail_requires_no_auth(self, client):
        """Thumbnail endpoint should work without auth (public asset)."""
        r = client.get("/thumbnails/test-video/1000.jpg")
        # Should return 404 (not 401) since thumbnails don't exist
        assert r.status_code == 404
