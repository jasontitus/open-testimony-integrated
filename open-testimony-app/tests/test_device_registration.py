"""Tests for device registration endpoint."""
import random


def test_register_new_device(api, base_url, device_id, public_key_pem):
    """Register a brand-new device."""
    r = api.post(
        f"{base_url}/register-device",
        data={
            "device_id": device_id,
            "public_key_pem": public_key_pem,
            "device_info": "pytest",
            "crypto_version": "hmac",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["device_id"] == device_id


def test_register_duplicate_device(api, base_url, registered_device):
    """Re-registering the same device should succeed (idempotent)."""
    device_id, public_key_pem = registered_device
    r = api.post(
        f"{base_url}/register-device",
        data={
            "device_id": device_id,
            "public_key_pem": public_key_pem,
            "crypto_version": "hmac",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"


def test_register_device_crypto_upgrade(api, base_url, registered_device):
    """Upgrading crypto_version should succeed."""
    device_id, public_key_pem = registered_device
    r = api.post(
        f"{base_url}/register-device",
        data={
            "device_id": device_id,
            "public_key_pem": public_key_pem,
            "crypto_version": "ecdsa",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "upgraded" in data.get("message", "").lower() or data["status"] == "success"


def test_register_missing_public_key(api, base_url):
    """Missing public_key_pem should return 422."""
    r = api.post(
        f"{base_url}/register-device",
        data={"device_id": f"bad-device-{random.randint(1,9999)}"},
    )
    assert r.status_code == 422
