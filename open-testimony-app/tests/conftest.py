"""
Shared fixtures for Open Testimony API tests.
Tests run against a live Docker Compose stack (API on localhost:18080).
"""
import hashlib
import json
import os
import base64
import hmac as hmac_mod
import random
import tempfile

import pytest
import requests

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:18080/api")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def api(base_url):
    """Requests session pointed at the API."""
    s = requests.Session()
    s.base_url = base_url
    # Verify API is reachable before running any tests
    try:
        r = requests.get(f"{base_url}/", timeout=5)
        r.raise_for_status()
    except Exception as e:
        pytest.skip(f"API not reachable at {base_url}: {e}")
    return s


@pytest.fixture(scope="session")
def signing_key():
    """Random 32-byte HMAC signing key (base64-encoded)."""
    key_bytes = bytes([random.randint(0, 255) for _ in range(32)])
    return base64.b64encode(key_bytes).decode()


@pytest.fixture(scope="session")
def device_id():
    """Unique device ID for this test run."""
    return f"pytest-device-{random.randint(10000, 99999)}"


@pytest.fixture(scope="session")
def public_key_pem(device_id):
    """MVP-format public key PEM for the test device."""
    public_key_data = f"DEVICE:{device_id}"
    public_key_b64 = base64.b64encode(public_key_data.encode()).decode()
    return f"-----BEGIN PUBLIC KEY-----\n{public_key_b64}\n-----END PUBLIC KEY-----"


@pytest.fixture(scope="session")
def registered_device(api, base_url, device_id, public_key_pem):
    """Register a device and return (device_id, public_key_pem)."""
    r = api.post(
        f"{base_url}/register-device",
        data={
            "device_id": device_id,
            "public_key_pem": public_key_pem,
            "device_info": "pytest",
            "crypto_version": "hmac",
        },
    )
    assert r.status_code == 200, f"Device registration failed: {r.text}"
    return device_id, public_key_pem


@pytest.fixture()
def test_video_file():
    """Create a temporary test video file, clean up after test."""
    fd, path = tempfile.mkstemp(suffix=".mp4")
    with os.fdopen(fd, "wb") as f:
        f.write(os.urandom(1024))
    yield path
    if os.path.exists(path):
        os.remove(path)


def make_signature(data: str, key_b64: str) -> str:
    """Create HMAC-SHA256 signature."""
    key_bytes = base64.b64decode(key_b64)
    sig = hmac_mod.new(key_bytes, data.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()


@pytest.fixture(scope="session")
def admin_session(base_url):
    """Login as admin and return a requests.Session with auth cookie."""
    s = requests.Session()
    r = s.post(f"{base_url}/auth/login", json={"username": "admin", "password": "admin"})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed (auth may not be set up): {r.text}")
    return s


@pytest.fixture(scope="session")
def staff_session(base_url, admin_session):
    """Ensure a staff user exists and return a logged-in session."""
    admin_session.post(f"{base_url}/auth/users", json={
        "username": "pytest-staff",
        "password": "testpass",
        "display_name": "Pytest Staff",
        "role": "staff",
    })
    s = requests.Session()
    r = s.post(f"{base_url}/auth/login", json={"username": "pytest-staff", "password": "testpass"})
    if r.status_code != 200:
        pytest.skip("Staff login failed")
    return s


def upload_test_media(
    api,
    base_url,
    device_id,
    public_key_pem,
    signing_key,
    file_path,
    source="live",
    media_type="video",
    exif_metadata=None,
):
    """Upload a file and return the response JSON."""
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    payload = {
        "video_hash": file_hash,
        "timestamp": "2026-02-08T12:00:00",
        "location": {"lat": 37.7749, "lon": -122.4194},
        "incident_tags": ["test"],
        "source": source,
        "media_type": media_type,
    }
    if exif_metadata:
        payload["exif_metadata"] = exif_metadata

    payload_json = json.dumps(payload, sort_keys=True)
    signature = make_signature(payload_json, signing_key)

    metadata = {
        "version": "1.0",
        "auth": {"device_id": device_id, "public_key_pem": public_key_pem},
        "payload": payload,
        "signature": signature,
    }

    with open(file_path, "rb") as f:
        r = api.post(
            f"{base_url}/upload",
            files={"video": ("test.mp4", f, "video/mp4")},
            data={"metadata": json.dumps(metadata)},
        )
    return r
