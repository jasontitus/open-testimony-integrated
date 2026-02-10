-- Migration 003: Add users table, audit user_id, video soft-delete

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'staff',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);

ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_id UUID;

ALTER TABLE videos ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS deleted_by UUID;
