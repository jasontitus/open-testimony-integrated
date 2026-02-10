"""Tests for the bridge webhook notification added to the upload endpoint."""
import hashlib
import json
import os
import sys
from io import BytesIO
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import make_upload_payload


class TestBridgeWebhookNotification:
    """The upload endpoint fires a webhook to the bridge service."""

    def test_upload_video_notifies_bridge(self, client, registered_device, mock_minio):
        """Video upload sends POST to bridge /hooks/video-uploaded."""
        video_bytes = b"fake-video-for-bridge-test"
        metadata, _ = make_upload_payload(video_bytes, registered_device)

        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("main.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            resp = client.post(
                "/upload",
                files={"video": ("test.mp4", BytesIO(video_bytes), "video/mp4")},
                data={"metadata": json.dumps(metadata)},
            )

        assert resp.status_code == 200

        # Verify the bridge was called
        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert "/hooks/video-uploaded" in call_args[0][0]
        webhook_body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "video_id" in webhook_body
        assert "object_name" in webhook_body

    def test_upload_photo_skips_bridge(self, client, registered_device, mock_minio):
        """Photo uploads do not trigger the bridge webhook (videos only)."""
        video_bytes = b"fake-photo-content"
        metadata, _ = make_upload_payload(video_bytes, registered_device)
        metadata["payload"]["media_type"] = "photo"

        with patch("main.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            resp = client.post(
                "/upload",
                files={"video": ("test.jpg", BytesIO(video_bytes), "image/jpeg")},
                data={"metadata": json.dumps(metadata)},
            )

        assert resp.status_code == 200
        # Bridge should NOT have been called for photos
        mock_client_instance.post.assert_not_called()

    def test_bridge_failure_is_nonfatal(self, client, registered_device, mock_minio):
        """Upload succeeds even when bridge notification fails."""
        video_bytes = b"video-when-bridge-down"
        metadata, _ = make_upload_payload(video_bytes, registered_device)

        with patch("main.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            resp = client.post(
                "/upload",
                files={"video": ("test.mp4", BytesIO(video_bytes), "video/mp4")},
                data={"metadata": json.dumps(metadata)},
            )

        # Upload should still succeed
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
