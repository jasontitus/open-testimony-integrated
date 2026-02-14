"""Tests for search query logging and analytics."""
import os
import sys
import uuid

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import CaptionEmbedding, SearchQuery, TranscriptEmbedding
from tests.conftest import insert_video_stub


class TestSearchQueryLogging:
    """Verify that search endpoints log queries to the search_queries table."""

    def test_visual_search_logs_query(self, client, auth_cookie, db_session):
        """Visual text search writes a row to search_queries (even with no results)."""
        resp = client.get(
            "/search/visual",
            params={"q": "person running"},
            cookies=auth_cookie,
        )
        assert resp.status_code == 200

        logs = db_session.query(SearchQuery).all()
        assert len(logs) == 1
        assert logs[0].query_text == "person running"
        assert logs[0].search_mode == "visual"
        assert logs[0].result_count >= 0
        assert logs[0].duration_ms >= 0

    def test_transcript_search_logs_query(self, client, auth_cookie, db_session):
        """Transcript semantic search writes a row to search_queries."""
        vid = insert_video_stub(db_session)
        db_session.add(
            TranscriptEmbedding(
                video_id=uuid.UUID(vid), segment_text="test segment",
                start_ms=0, end_ms=1000,
                embedding=np.random.randn(4096).tolist(),
            )
        )
        db_session.commit()

        resp = client.get(
            "/search/transcript",
            params={"q": "police encounter"},
            cookies=auth_cookie,
        )
        assert resp.status_code == 200

        logs = db_session.query(SearchQuery).all()
        assert len(logs) == 1
        assert logs[0].query_text == "police encounter"
        assert logs[0].search_mode == "transcript"

    def test_transcript_exact_logs_query(self, client, auth_cookie, db_session):
        """Transcript exact search writes a row to search_queries."""
        vid = insert_video_stub(db_session)
        db_session.add(
            TranscriptEmbedding(
                video_id=uuid.UUID(vid), segment_text="the officer stopped",
                start_ms=0, end_ms=1000,
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

        logs = db_session.query(SearchQuery).all()
        assert len(logs) == 1
        assert logs[0].query_text == "officer"
        assert logs[0].search_mode == "transcript_exact"
        assert logs[0].result_count == 1

    def test_caption_search_logs_query(self, client, auth_cookie, db_session):
        """Caption semantic search writes a row to search_queries."""
        resp = client.get(
            "/search/captions",
            params={"q": "red hat"},
            cookies=auth_cookie,
        )
        assert resp.status_code == 200

        logs = db_session.query(SearchQuery).all()
        assert len(logs) == 1
        assert logs[0].query_text == "red hat"
        assert logs[0].search_mode == "caption"

    def test_caption_exact_logs_query(self, client, auth_cookie, db_session):
        """Caption exact search writes a row to search_queries."""
        vid = insert_video_stub(db_session)
        db_session.add(
            CaptionEmbedding(
                video_id=uuid.UUID(vid), frame_num=0, timestamp_ms=0,
                caption_text="A person in a red hat",
                embedding=np.random.randn(4096).tolist(),
            )
        )
        db_session.commit()

        resp = client.get(
            "/search/captions/exact",
            params={"q": "red hat"},
            cookies=auth_cookie,
        )
        assert resp.status_code == 200

        logs = db_session.query(SearchQuery).all()
        assert len(logs) == 1
        assert logs[0].query_text == "red hat"
        assert logs[0].search_mode == "caption_exact"
        assert logs[0].result_count == 1

    def test_combined_search_logs_query(self, client, auth_cookie, db_session):
        """Combined search writes a single row to search_queries."""
        resp = client.get(
            "/search/combined",
            params={"q": "protest march"},
            cookies=auth_cookie,
        )
        assert resp.status_code == 200

        logs = db_session.query(SearchQuery).all()
        assert len(logs) == 1
        assert logs[0].query_text == "protest march"
        assert logs[0].search_mode == "combined"

    def test_multiple_searches_logged_separately(self, client, auth_cookie, db_session):
        """Each search creates its own log entry."""
        for q in ["first query", "second query", "third query"]:
            client.get(
                "/search/captions",
                params={"q": q},
                cookies=auth_cookie,
            )

        logs = db_session.query(SearchQuery).order_by(SearchQuery.id).all()
        assert len(logs) == 3
        assert logs[0].query_text == "first query"
        assert logs[1].query_text == "second query"
        assert logs[2].query_text == "third query"

    def test_zero_result_search_logged(self, client, auth_cookie, db_session):
        """Searches with no results still get logged with result_count=0."""
        resp = client.get(
            "/search/visual",
            params={"q": "nonexistent thing"},
            cookies=auth_cookie,
        )
        assert resp.status_code == 200
        assert resp.json()["results"] == []

        logs = db_session.query(SearchQuery).all()
        assert len(logs) == 1
        assert logs[0].result_count == 0


class TestSearchQueryModel:
    """Test the SearchQuery model properties."""

    def test_no_ip_or_pii_columns(self):
        """SearchQuery model must not have IP or user_agent columns (privacy)."""
        columns = {c.name for c in SearchQuery.__table__.columns}
        assert "client_ip" not in columns
        assert "user_agent" not in columns
        assert "ip" not in columns

    def test_required_columns_exist(self):
        """SearchQuery has the expected analytics columns."""
        columns = {c.name for c in SearchQuery.__table__.columns}
        assert "query_text" in columns
        assert "search_mode" in columns
        assert "result_count" in columns
        assert "duration_ms" in columns
        assert "created_at" in columns

    def test_create_search_query(self, db_session):
        """Can create and read back a SearchQuery."""
        entry = SearchQuery(
            query_text="test query",
            search_mode="visual",
            result_count=5,
            duration_ms=120,
        )
        db_session.add(entry)
        db_session.commit()

        result = db_session.query(SearchQuery).first()
        assert result.query_text == "test query"
        assert result.search_mode == "visual"
        assert result.result_count == 5
        assert result.duration_ms == 120
        assert result.created_at is not None
