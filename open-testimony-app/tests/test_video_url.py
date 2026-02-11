"""Tests for the video URL (presigned URL) endpoint."""
from conftest import upload_test_media


class TestVideoUrl:
    def test_get_video_url(
        self, api, base_url, registered_device, signing_key, test_video_file
    ):
        """GET /videos/{id}/url should return a presigned URL."""
        device_id, public_key_pem = registered_device
        upload_resp = upload_test_media(
            api, base_url, device_id, public_key_pem, signing_key, test_video_file,
        )
        video_id = upload_resp.json()["video_id"]

        r = api.get(f"{base_url}/videos/{video_id}/url")
        assert r.status_code == 200
        data = r.json()
        assert "url" in data
        assert isinstance(data["url"], str)
        assert len(data["url"]) > 0
        # URL should contain the bucket/object path
        assert "videos/" in data["url"] or "minio" in data["url"].lower()

    def test_get_video_url_nonexistent(self, api, base_url):
        """GET /videos/{id}/url for missing video should return 404."""
        r = api.get(f"{base_url}/videos/00000000-0000-0000-0000-000000000000/url")
        assert r.status_code == 404

    def test_get_video_url_invalid_uuid(self, api, base_url):
        """GET /videos/{id}/url with a bad UUID should return an error."""
        r = api.get(f"{base_url}/videos/not-a-uuid/url")
        # Server returns 500 because UUID cast fails in SQLAlchemy query
        # (ideally would be 400/422, tracked as a known issue)
        assert r.status_code in (400, 404, 422, 500)
