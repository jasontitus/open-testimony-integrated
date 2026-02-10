"""Tests for the bridge health endpoint."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHealthEndpoint:
    """GET /health returns service status."""

    def test_health_returns_200(self, client):
        """Health check is publicly accessible."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_reports_model_status(self, client):
        """Health response includes model loading status."""
        resp = client.get("/health")
        body = resp.json()
        assert "status" in body
        assert body["status"] == "healthy"
        assert "vision_model_loaded" in body
        assert "text_model_loaded" in body
