"""Tests for audit chain verification — must survive pagination refactor."""
import hashlib
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import audit_service
from models import AuditLog

GENESIS_HASH = "0" * 64


class TestAuditChainVerification:
    """Verify that verify_chain() correctly validates the hash chain."""

    def test_empty_chain_is_valid(self, db_session):
        """An empty audit log should verify as valid."""
        result = audit_service.verify_chain(db_session)
        assert result["valid"] is True
        assert result["entries_checked"] == 0
        assert result["errors"] == []

    def test_single_entry_chain(self, db_session):
        """A single-entry chain should verify."""
        audit_service.log_event(
            db_session, "test_event", {"key": "value"}
        )
        db_session.commit()

        result = audit_service.verify_chain(db_session)
        assert result["valid"] is True
        assert result["entries_checked"] == 1

    def test_multi_entry_chain(self, db_session):
        """A chain with multiple entries should verify correctly."""
        for i in range(10):
            audit_service.log_event(
                db_session, "test_event", {"index": i}
            )
            db_session.commit()

        result = audit_service.verify_chain(db_session)
        assert result["valid"] is True
        assert result["entries_checked"] == 10

    def test_large_chain(self, db_session):
        """A chain with many entries should verify (tests pagination works)."""
        for i in range(150):
            audit_service.log_event(
                db_session, "bulk_event", {"i": i}
            )
        db_session.commit()

        result = audit_service.verify_chain(db_session)
        assert result["valid"] is True
        assert result["entries_checked"] == 150

    def test_tampered_entry_detected(self, db_session):
        """Modifying an entry's data should break verification."""
        for i in range(5):
            audit_service.log_event(
                db_session, "test_event", {"index": i}
            )
            db_session.commit()

        # Tamper with the 3rd entry's event_data
        entry = (
            db_session.query(AuditLog)
            .filter(AuditLog.sequence_number == 3)
            .first()
        )
        entry.event_data = {"index": 999, "tampered": True}
        db_session.commit()

        result = audit_service.verify_chain(db_session)
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        # The tampered entry should be flagged
        error_seqs = [e["sequence_number"] for e in result["errors"]]
        assert 3 in error_seqs

    def test_broken_hash_link_detected(self, db_session):
        """Changing an entry's previous_hash should be detected."""
        for i in range(5):
            audit_service.log_event(
                db_session, "test_event", {"index": i}
            )
            db_session.commit()

        entry = (
            db_session.query(AuditLog)
            .filter(AuditLog.sequence_number == 4)
            .first()
        )
        entry.previous_hash = "deadbeef" * 8
        db_session.commit()

        result = audit_service.verify_chain(db_session)
        assert result["valid"] is False

    def test_verify_endpoint(self, client, db_session):
        """The /audit-log/verify endpoint returns chain status."""
        audit_service.log_event(
            db_session, "test_event", {"from": "endpoint_test"}
        )
        db_session.commit()

        resp = client.get("/audit-log/verify")
        assert resp.status_code == 200
        body = resp.json()
        assert "valid" in body
        assert "entries_checked" in body


class TestAuditLogEvent:
    """Verify log_event produces correct chain linkage."""

    def test_first_entry_uses_genesis(self, db_session):
        """First entry should link to the genesis hash."""
        entry = audit_service.log_event(
            db_session, "first", {"data": 1}
        )
        db_session.commit()

        assert entry.previous_hash == GENESIS_HASH
        assert entry.sequence_number == 1
        assert entry.entry_hash is not None

    def test_entries_chain_correctly(self, db_session):
        """Each entry's previous_hash should match the prior entry's entry_hash."""
        e1 = audit_service.log_event(db_session, "event1", {"a": 1})
        db_session.commit()
        e2 = audit_service.log_event(db_session, "event2", {"b": 2})
        db_session.commit()

        assert e2.previous_hash == e1.entry_hash
        assert e2.sequence_number == e1.sequence_number + 1
