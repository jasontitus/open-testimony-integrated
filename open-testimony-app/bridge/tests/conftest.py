"""Test fixtures for the AI Search Bridge Service tests."""
import os
import sys
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add bridge root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from models import Base, FrameEmbedding, TranscriptEmbedding, VideoIndexStatus

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://user:pass@db:5432/opentestimony_test",
)


@pytest.fixture(scope="session")
def db_engine():
    """Create a test database engine and tables."""
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    # Create pgvector extension (may already exist)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session")
def TestingSessionLocal(db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture(autouse=True)
def clean_tables(db_engine):
    """Truncate bridge tables between tests."""
    yield
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM frame_embeddings"))
        conn.execute(text("DELETE FROM transcript_embeddings"))
        conn.execute(text("DELETE FROM video_index_status"))
        conn.commit()


@pytest.fixture
def db_session(TestingSessionLocal):
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_vision_model():
    """Mock vision model that returns fake embeddings."""
    model = MagicMock()
    # OpenCLIP-style encode_image
    model.encode_image = MagicMock(
        side_effect=lambda x: _fake_tensor(x.shape[0], 768)
    )
    # OpenCLIP-style encode_text
    model.encode_text = MagicMock(
        side_effect=lambda x: _fake_tensor(x.shape[0], 768)
    )
    return model


@pytest.fixture
def mock_vision_preprocess():
    """Mock image preprocessor that returns a dummy tensor."""
    import torch

    def preprocess(img):
        return torch.randn(3, 224, 224)

    return preprocess


@pytest.fixture
def mock_text_model():
    """Mock SentenceTransformer that returns fake embeddings."""
    model = MagicMock()
    model.encode = MagicMock(
        side_effect=lambda texts, **kwargs: np.random.randn(len(texts), 4096).astype(
            np.float32
        )
    )
    model.get_sentence_embedding_dimension = MagicMock(return_value=4096)
    return model


@pytest.fixture
def mock_minio():
    """Mock MinIO client."""
    client = MagicMock()
    client.fget_object = MagicMock(return_value=None)
    client.bucket_exists = MagicMock(return_value=True)
    return client


def _fake_tensor(batch_size, dim):
    """Create a fake torch tensor of normalized embeddings."""
    import torch

    t = torch.randn(batch_size, dim)
    return torch.nn.functional.normalize(t, dim=-1)


@pytest.fixture
def app(TestingSessionLocal, mock_vision_model, mock_vision_preprocess, mock_text_model):
    """Create a FastAPI test app with mocked models and DB."""
    import main as bridge_main

    # Inject mock models
    bridge_main.vision_model = mock_vision_model
    bridge_main.vision_preprocess = mock_vision_preprocess
    bridge_main.text_model = mock_text_model

    # Override DB session
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Patch lifespan so it doesn't load real models or start worker
    original_lifespan = bridge_main.app.router.lifespan_context

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    bridge_main.app.router.lifespan_context = noop_lifespan
    bridge_main.app.dependency_overrides[bridge_main.get_db] = override_get_db

    # Also override the search router's get_db
    from search.router import get_db as search_get_db

    bridge_main.app.dependency_overrides[search_get_db] = override_get_db

    yield bridge_main.app

    bridge_main.app.dependency_overrides.clear()
    bridge_main.app.router.lifespan_context = original_lifespan


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def auth_cookie():
    """Create a valid JWT cookie matching the bridge's JWT config."""
    token = jwt.encode(
        {"sub": "testuser", "exp": datetime(2099, 1, 1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"access_token": token}


@pytest.fixture
def sample_video_id():
    """A consistent test video UUID."""
    return str(uuid.uuid4())


def insert_video_stub(db_session, video_id=None):
    """Insert a minimal videos row (needed for FK references).

    This creates a row directly in the videos table since the bridge
    doesn't own that table but needs FKs to it.
    """
    vid = video_id or str(uuid.uuid4())
    db_session.execute(
        text("""
            INSERT INTO videos (id, device_id, object_name, file_hash, timestamp,
                                latitude, longitude, verification_status,
                                metadata_json, uploaded_at)
            VALUES (:id, 'test-device', 'videos/test/test.mp4',
                    :hash, NOW(), 40.7128, -74.006, 'verified',
                    '{}', NOW())
            ON CONFLICT (id) DO NOTHING
        """),
        {"id": vid, "hash": "a" * 64},
    )
    db_session.commit()
    return vid
