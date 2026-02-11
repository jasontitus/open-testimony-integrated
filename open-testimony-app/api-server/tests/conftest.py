"""Test fixtures for the Open Testimony API tests."""
import hashlib
import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent dir to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, get_db
from models import Device, Video, AuditLog, User

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://user:pass@db:5432/opentestimony_test",
)


@pytest.fixture(scope="session")
def db_engine():
    """Create a test database engine."""
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session")
def TestingSessionLocal(db_engine):
    """Shared session factory for the test database."""
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture(autouse=True)
def clean_tables(db_engine):
    """Truncate all tables between tests for isolation."""
    yield
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM audit_log"))
        conn.execute(text("DELETE FROM videos"))
        conn.execute(text("DELETE FROM devices"))
        conn.execute(text("DELETE FROM users"))
        conn.commit()


@pytest.fixture
def db_session(TestingSessionLocal):
    """Create a test database session."""
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_minio():
    """Mock MinIO client that records calls."""
    mock_client = MagicMock()
    mock_client.put_object = MagicMock(return_value=None)
    mock_client.bucket_exists = MagicMock(return_value=True)
    mock_client.get_presigned_url = MagicMock(
        return_value="http://minio:9000/bucket/obj?sig=abc"
    )
    return mock_client


@pytest.fixture
def app(TestingSessionLocal, mock_minio):
    """Create a FastAPI test app with overridden dependencies."""

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    with patch("main.get_minio_client", return_value=mock_minio), \
         patch("minio_client.get_minio_client", return_value=mock_minio), \
         patch("minio_client.ensure_bucket_exists", return_value=None):
        from main import app as fastapi_app

        fastapi_app.dependency_overrides[get_db] = override_get_db
        yield fastapi_app
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    """Create a test HTTP client."""
    return TestClient(app)


@pytest.fixture
def registered_device(db_session):
    """Insert a registered test device."""
    device = Device(
        device_id="test-device-001",
        public_key_pem="-----BEGIN PUBLIC KEY-----\nDEVICE:test-device-001\n-----END PUBLIC KEY-----",
        device_info="Test device",
        registered_at=datetime.utcnow(),
        crypto_version="hmac",
    )
    db_session.add(device)
    db_session.commit()
    return device.device_id


@pytest.fixture
def admin_user(db_session):
    """Insert an admin user and return the User object."""
    from auth import hash_password
    user = User(
        username="test-admin",
        password_hash=hash_password("testpass"),
        display_name="Test Admin",
        role="admin",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_client(app, admin_user):
    """TestClient with an admin auth cookie set."""
    from auth import create_access_token
    token = create_access_token({"sub": admin_user.username})
    c = TestClient(app)
    c.cookies.set("access_token", token)
    return c


def make_upload_payload(video_bytes: bytes, device_id: str = "test-device-001"):
    """Build the metadata JSON and video bytes for an upload request."""
    file_hash = hashlib.sha256(video_bytes).hexdigest()
    payload = {
        "video_hash": file_hash,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "location": {"lat": 40.7128, "lon": -74.0060},
        "incident_tags": ["test"],
        "source": "live",
    }
    metadata = {
        "version": "1.0",
        "auth": {
            "device_id": device_id,
            "public_key_pem": "-----BEGIN PUBLIC KEY-----\nDEVICE:test-device-001\n-----END PUBLIC KEY-----",
        },
        "payload": payload,
        "signature": "dGVzdC1zaWduYXR1cmU=",
    }
    return metadata, video_bytes
