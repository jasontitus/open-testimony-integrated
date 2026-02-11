"""Tests for search endpoints (visual + transcript)."""
import os
import sys
import uuid
from unittest.mock import patch, MagicMock

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import FrameEmbedding, TranscriptEmbedding
from tests.conftest import insert_video_stub


def _make_open_clip_mock():
    """Create a configured open_clip mock with a tokenizer that returns a real tensor."""
    mock_oc = MagicMock()
    mock_tokenizer = MagicMock(return_value=torch.zeros(1, 77, dtype=torch.long))
    mock_oc.get_tokenizer.return_value = mock_tokenizer
    return mock_oc


class TestVisualTextSearch:
    """GET /search/visual?q=... text-to-video search."""

    def test_search_returns_results(self, client, auth_cookie, db_session):
        """Visual text search returns matching frame embeddings."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        # Insert frame embeddings
        for i in range(5):
            db_session.add(
                FrameEmbedding(
                    video_id=video_uuid,
                    frame_num=i,
                    timestamp_ms=i * 2000,
                    embedding=np.random.randn(1280).tolist(),
                )
            )
        db_session.commit()

        with patch.dict(sys.modules, {"open_clip": _make_open_clip_mock()}):
            resp = client.get(
                "/search/visual",
                params={"q": "a person walking", "limit": 3},
                cookies=auth_cookie,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "a person walking"
        assert body["mode"] == "visual_text"
        assert len(body["results"]) <= 3
        for r in body["results"]:
            assert "video_id" in r
            assert "timestamp_ms" in r
            assert "score" in r

    def test_search_empty_query_rejected(self, client, auth_cookie):
        """Empty query string is rejected with 422."""
        resp = client.get(
            "/search/visual", params={"q": ""}, cookies=auth_cookie
        )
        assert resp.status_code == 422

    def test_search_no_results(self, client, auth_cookie):
        """Search with no indexed videos returns empty results."""
        with patch.dict(sys.modules, {"open_clip": _make_open_clip_mock()}):
            resp = client.get(
                "/search/visual",
                params={"q": "something"},
                cookies=auth_cookie,
            )

        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_search_requires_auth(self, client):
        """Visual search requires JWT auth."""
        resp = client.get("/search/visual", params={"q": "test"})
        assert resp.status_code == 401


class TestVisualImageSearch:
    """POST /search/visual image-to-video search."""

    def test_image_search(self, client, auth_cookie, db_session):
        """Image upload search returns frame results."""
        vid = insert_video_stub(db_session)
        for i in range(3):
            db_session.add(
                FrameEmbedding(
                    video_id=uuid.UUID(vid),
                    frame_num=i,
                    timestamp_ms=i * 1000,
                    embedding=np.random.randn(1280).tolist(),
                )
            )
        db_session.commit()

        # Create a minimal valid JPEG
        import io
        from PIL import Image

        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        resp = client.post(
            "/search/visual",
            files={"image": ("test.jpg", buf, "image/jpeg")},
            cookies=auth_cookie,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "visual_image"
        assert isinstance(body["results"], list)


class TestTranscriptSemanticSearch:
    """GET /search/transcript?q=... semantic transcript search."""

    def test_semantic_search_returns_results(self, client, auth_cookie, db_session):
        """Semantic transcript search returns matching segments."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        segments = [
            ("The officer approached the vehicle", 0, 3000),
            ("The protest started at noon", 3000, 6000),
            ("Witness described the incident", 6000, 9000),
        ]
        for seg_text, start, end in segments:
            db_session.add(
                TranscriptEmbedding(
                    video_id=video_uuid,
                    segment_text=seg_text,
                    start_ms=start,
                    end_ms=end,
                    embedding=np.random.randn(4096).tolist(),
                )
            )
        db_session.commit()

        resp = client.get(
            "/search/transcript",
            params={"q": "police traffic stop", "limit": 10},
            cookies=auth_cookie,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "transcript_semantic"
        assert len(body["results"]) <= 10
        for r in body["results"]:
            assert "video_id" in r
            assert "segment_text" in r
            assert "start_ms" in r
            assert "end_ms" in r
            assert "score" in r

    def test_semantic_search_requires_auth(self, client):
        """Transcript search requires JWT auth."""
        resp = client.get("/search/transcript", params={"q": "test"})
        assert resp.status_code == 401


class TestTranscriptExactSearch:
    """GET /search/transcript/exact?q=... exact text search."""

    def test_exact_search_finds_matches(self, client, auth_cookie, db_session):
        """Exact search finds segments containing the query string."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        db_session.add(
            TranscriptEmbedding(
                video_id=video_uuid,
                segment_text="The officer said stop right there",
                start_ms=0,
                end_ms=2000,
                embedding=np.random.randn(4096).tolist(),
            )
        )
        db_session.add(
            TranscriptEmbedding(
                video_id=video_uuid,
                segment_text="The weather was nice that day",
                start_ms=2000,
                end_ms=4000,
                embedding=np.random.randn(4096).tolist(),
            )
        )
        db_session.commit()

        resp = client.get(
            "/search/transcript/exact",
            params={"q": "officer"},
            cookies=auth_cookie,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "transcript_exact"
        assert len(body["results"]) == 1
        assert "officer" in body["results"][0]["segment_text"].lower()

    def test_exact_search_case_insensitive(self, client, auth_cookie, db_session):
        """Exact search is case-insensitive (ILIKE)."""
        vid = insert_video_stub(db_session)
        db_session.add(
            TranscriptEmbedding(
                video_id=uuid.UUID(vid),
                segment_text="LOUD SHOUTING was heard",
                start_ms=0,
                end_ms=1000,
                embedding=np.random.randn(4096).tolist(),
            )
        )
        db_session.commit()

        resp = client.get(
            "/search/transcript/exact",
            params={"q": "loud shouting"},
            cookies=auth_cookie,
        )

        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1

    def test_exact_search_no_match(self, client, auth_cookie, db_session):
        """Exact search returns empty when no segments match."""
        vid = insert_video_stub(db_session)
        db_session.add(
            TranscriptEmbedding(
                video_id=uuid.UUID(vid),
                segment_text="Nothing relevant here",
                start_ms=0,
                end_ms=1000,
                embedding=np.random.randn(4096).tolist(),
            )
        )
        db_session.commit()

        resp = client.get(
            "/search/transcript/exact",
            params={"q": "xyznonexistent"},
            cookies=auth_cookie,
        )

        assert resp.status_code == 200
        assert resp.json()["results"] == []
