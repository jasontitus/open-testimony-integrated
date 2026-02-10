"""Audit service for blockchain-like immutable hash-chained log"""
import hashlib
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import AuditLog

GENESIS_HASH = "0" * 64


def log_event(
    db: Session,
    event_type: str,
    event_data: dict,
    video_id: Optional[str] = None,
    device_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> AuditLog:
    """Append an event to the audit chain with hash linking."""
    # Get the last entry (use FOR UPDATE to prevent race conditions)
    last_entry = (
        db.query(AuditLog)
        .order_by(AuditLog.sequence_number.desc())
        .with_for_update()
        .first()
    )

    if last_entry:
        previous_hash = last_entry.entry_hash
        next_sequence = last_entry.sequence_number + 1
    else:
        previous_hash = GENESIS_HASH
        next_sequence = 1

    now = datetime.utcnow()

    # Build the content to hash: sequence + event_type + event_data + previous_hash + timestamp
    hash_content = json.dumps(
        {
            "sequence_number": next_sequence,
            "event_type": event_type,
            "event_data": event_data,
            "previous_hash": previous_hash,
            "created_at": now.isoformat(),
        },
        sort_keys=True,
    )
    entry_hash = hashlib.sha256(hash_content.encode()).hexdigest()

    # Include user_id in event_data for traceability (not in hash formula)
    if user_id:
        event_data = {**event_data, "user_id": user_id}

    entry = AuditLog(
        sequence_number=next_sequence,
        event_type=event_type,
        video_id=video_id,
        device_id=device_id,
        event_data=event_data,
        entry_hash=entry_hash,
        previous_hash=previous_hash,
        created_at=now,
        user_id=user_id,
    )
    db.add(entry)
    db.flush()  # Flush so the entry is visible but let caller commit

    return entry


def verify_chain(db: Session, batch_size: int = 1000) -> dict:
    """Walk the entire audit chain in batches and verify all hashes."""
    errors = []
    expected_previous = GENESIS_HASH
    entries_checked = 0
    last_seq = 0

    while True:
        batch = (
            db.query(AuditLog)
            .filter(AuditLog.sequence_number > last_seq)
            .order_by(AuditLog.sequence_number.asc())
            .limit(batch_size)
            .all()
        )

        if not batch:
            break

        for entry in batch:
            # Check previous_hash link
            if entry.previous_hash != expected_previous:
                errors.append(
                    {
                        "sequence_number": entry.sequence_number,
                        "error": "previous_hash mismatch",
                        "expected": expected_previous,
                        "actual": entry.previous_hash,
                    }
                )

            # Recompute entry hash (strip user_id from event_data — it's added after hashing)
            verify_event_data = {k: v for k, v in entry.event_data.items() if k != "user_id"}
            hash_content = json.dumps(
                {
                    "sequence_number": entry.sequence_number,
                    "event_type": entry.event_type,
                    "event_data": verify_event_data,
                    "previous_hash": entry.previous_hash,
                    "created_at": entry.created_at.isoformat(),
                },
                sort_keys=True,
            )
            recomputed = hashlib.sha256(hash_content.encode()).hexdigest()

            if recomputed != entry.entry_hash:
                errors.append(
                    {
                        "sequence_number": entry.sequence_number,
                        "error": "entry_hash mismatch",
                        "expected": recomputed,
                        "actual": entry.entry_hash,
                    }
                )

            expected_previous = entry.entry_hash
            entries_checked += 1

        last_seq = batch[-1].sequence_number

        # Free ORM objects from session identity map to cap memory
        db.expire_all()

    return {
        "valid": len(errors) == 0,
        "entries_checked": entries_checked,
        "errors": errors,
    }
