"""Tests for health and root endpoints."""


def test_root_endpoint(api, base_url):
    r = api.get(f"{base_url}/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "operational"
    assert "version" in data


def test_health_endpoint(api, base_url):
    r = api.get(f"{base_url}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
