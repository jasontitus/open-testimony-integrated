"""Tests for search endpoints (visual + transcript + caption + combined)."""
import os
import sys
import uuid

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import CaptionEmbedding, FrameEmbedding, TranscriptEmbedding
from tests.conftest import insert_video_stub


class TestVisualTextSearch:
    """GET /search/visual?q=... text-to-video search."""

    def test_search_returns_results(self, client, auth_cookie, db_session):
        """Visual text search returns matching frame embeddings."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        # Insert frame embeddings (1152-dim for SigLIP)
        for i in range(5):
            db_session.add(
                FrameEmbedding(
                    video_id=video_uuid,
                    frame_num=i,
                    timestamp_ms=i * 2000,
                    embedding=np.random.randn(1152).tolist(),
                )
            )
        db_session.commit()

        resp = client.get(
            "/search/visual",
            params={"q": "a person walking", "limit": 3},
            cookies=auth_cookie,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "a person walking"
        assert body["mode"] == "visual_text"
        assert "timing" in body
        assert "total_ms" in body["timing"]
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
                    embedding=np.random.randn(1152).tolist(),
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
        assert "timing" in body
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
        assert "timing" in body
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
        assert "timing" in body
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


class TestCaptionSearch:
    """GET /search/captions?q=... caption semantic search."""

    def test_caption_search_returns_results(self, client, auth_cookie, db_session):
        """Caption search returns matching caption embeddings."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        captions = [
            (0, 0, "A person wearing a red baseball cap walking down the street"),
            (1, 2000, "Two officers standing near a patrol car"),
            (2, 4000, "A crowd gathered at the intersection"),
        ]
        for frame_num, ts, cap_text in captions:
            db_session.add(
                CaptionEmbedding(
                    video_id=video_uuid,
                    frame_num=frame_num,
                    timestamp_ms=ts,
                    caption_text=cap_text,
                    embedding=np.random.randn(4096).tolist(),
                )
            )
        db_session.commit()

        resp = client.get(
            "/search/captions",
            params={"q": "red hat", "limit": 10},
            cookies=auth_cookie,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "caption_semantic"
        assert body["query"] == "red hat"
        assert "timing" in body
        assert "encode_ms" in body["timing"]
        assert "caption_search_ms" in body["timing"]
        assert "total_ms" in body["timing"]
        assert len(body["results"]) <= 10
        for r in body["results"]:
            assert "video_id" in r
            assert "timestamp_ms" in r
            assert "frame_num" in r
            assert "caption_text" in r
            assert "score" in r

    def test_caption_search_requires_auth(self, client):
        """Caption search requires JWT auth."""
        resp = client.get("/search/captions", params={"q": "test"})
        assert resp.status_code == 401

    def test_caption_search_empty_returns_empty(self, client, auth_cookie):
        """Caption search with no data returns empty results."""
        resp = client.get(
            "/search/captions",
            params={"q": "something"},
            cookies=auth_cookie,
        )

        assert resp.status_code == 200
        assert resp.json()["results"] == []


class TestCombinedSearch:
    """GET /search/combined?q=... combined visual + caption search."""

    def test_combined_search_returns_results(self, client, auth_cookie, db_session):
        """Combined search returns results with source field and timing metadata."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        # Insert frame embeddings (visual path)
        for i in range(3):
            db_session.add(
                FrameEmbedding(
                    video_id=video_uuid,
                    frame_num=i,
                    timestamp_ms=i * 2000,
                    embedding=np.random.randn(1152).tolist(),
                )
            )

        # Insert caption embeddings (caption path)
        for i in range(3):
            db_session.add(
                CaptionEmbedding(
                    video_id=video_uuid,
                    frame_num=i,
                    timestamp_ms=i * 2000,
                    caption_text=f"Frame {i} description",
                    embedding=np.random.randn(4096).tolist(),
                )
            )
        db_session.commit()

        resp = client.get(
            "/search/combined",
            params={"q": "red hat", "limit": 10},
            cookies=auth_cookie,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "combined"
        assert body["query"] == "red hat"

        # Timing metadata
        assert "timing" in body
        timing = body["timing"]
        assert "encode_ms" in timing
        assert "visual_search_ms" in timing
        assert "caption_search_ms" in timing
        assert "total_ms" in timing

        # Results have source field
        assert len(body["results"]) > 0
        for r in body["results"]:
            assert "video_id" in r
            assert "score" in r
            assert "source" in r
            assert r["source"] in ("visual", "caption", "both")

    def test_combined_search_dedup(self, client, auth_cookie, db_session):
        """Combined search deduplicates results by (video_id, frame_num) and keeps both scores."""
        vid = insert_video_stub(db_session)
        video_uuid = uuid.UUID(vid)

        # Same frame in both visual and caption indexes
        db_session.add(
            FrameEmbedding(
                video_id=video_uuid,
                frame_num=0,
                timestamp_ms=0,
                embedding=np.random.randn(1152).tolist(),
            )
        )
        db_session.add(
            CaptionEmbedding(
                video_id=video_uuid,
                frame_num=0,
                timestamp_ms=0,
                caption_text="A person in a red hat",
                embedding=np.random.randn(4096).tolist(),
            )
        )
        db_session.commit()

        resp = client.get(
            "/search/combined",
            params={"q": "red hat", "limit": 10},
            cookies=auth_cookie,
        )

        assert resp.status_code == 200
        body = resp.json()
        # Should be deduplicated to 1 result
        frame_0_results = [r for r in body["results"] if r["frame_num"] == 0]
        assert len(frame_0_results) == 1
        r = frame_0_results[0]
        # Should have both visual_score and caption_score
        assert "visual_score" in r
        assert "caption_score" in r

    def test_combined_search_requires_auth(self, client):
        """Combined search requires JWT auth."""
        resp = client.get("/search/combined", params={"q": "test"})
        assert resp.status_code == 401
