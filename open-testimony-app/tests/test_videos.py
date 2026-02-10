"""Tests for video listing and detail endpoints."""
from conftest import upload_test_media


class TestVideoList:
    def test_list_videos(self, api, base_url):
        r = api.get(f"{base_url}/videos")
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert "videos" in data
        assert isinstance(data["videos"], list)

    def test_list_videos_has_new_fields(self, api, base_url):
        """Verify list response includes source, media_type, category."""
        r = api.get(f"{base_url}/videos")
        assert r.status_code == 200
        videos = r.json()["videos"]
        if videos:
            v = videos[0]
            assert "source" in v
            assert "media_type" in v
            assert "category" in v

    def test_list_videos_with_device_filter(self, api, base_url, registered_device):
        device_id, _ = registered_device
        r = api.get(f"{base_url}/videos", params={"device_id": device_id})
        assert r.status_code == 200
        for v in r.json()["videos"]:
            assert v["device_id"] == device_id

    def test_list_videos_pagination(self, api, base_url):
        r = api.get(f"{base_url}/videos", params={"limit": 2, "offset": 0})
        assert r.status_code == 200
        assert len(r.json()["videos"]) <= 2


class TestVideoDetail:
    def test_get_video_detail(
        self, api, base_url, registered_device, signing_key, test_video_file
    ):
        device_id, public_key_pem = registered_device
        upload_resp = upload_test_media(
            api, base_url, device_id, public_key_pem, signing_key, test_video_file,
        )
        video_id = upload_resp.json()["video_id"]

        r = api.get(f"{base_url}/videos/{video_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == video_id
        assert data["device_id"] == device_id
        assert "file_hash" in data
        assert "source" in data
        assert "media_type" in data
        assert "category" in data
        assert "location_description" in data
        assert "notes" in data
        assert "exif_metadata" in data

    def test_get_nonexistent_video(self, api, base_url):
        r = api.get(f"{base_url}/videos/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404
