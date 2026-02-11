"""Tests for the thumbnail serving endpoint."""
import os


class TestThumbnailEndpoint:
    def test_exact_thumbnail_found(self, client, auth_cookie):
        """GET /thumbnails/{id}/{ts}.jpg returns 200 when file exists."""
        video_id = "test-thumb-video"
        thumb_dir = f"/data/thumbnails/{video_id}"
        thumb_path = os.path.join(thumb_dir, "5000.jpg")

        os.makedirs(thumb_dir, exist_ok=True)
        try:
            with open(thumb_path, "wb") as f:
                f.write(b"\xff\xd8\xff\xe0JFIF" + b"\x00" * 100)

            r = client.get(
                f"/thumbnails/{video_id}/5000.jpg",
                cookies=auth_cookie,
            )
            assert r.status_code == 200
            assert r.headers["content-type"] == "image/jpeg"
        finally:
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            if os.path.isdir(thumb_dir):
                os.rmdir(thumb_dir)

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
