-- Migration 002: Create audit_log table for blockchain-like immutable log
-- Idempotent: safe to run multiple times

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_number INTEGER UNIQUE NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    video_id UUID,
    device_id VARCHAR(255),
    event_data JSONB NOT NULL,
    entry_hash VARCHAR(64) NOT NULL,
    previous_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_audit_log_sequence_number ON audit_log (sequence_number);
CREATE INDEX IF NOT EXISTS ix_audit_log_event_type ON audit_log (event_type);
CREATE INDEX IF NOT EXISTS ix_audit_log_video_id ON audit_log (video_id);
