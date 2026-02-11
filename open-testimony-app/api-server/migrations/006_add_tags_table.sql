-- Migration 006: Add persistent tags table

CREATE TABLE IF NOT EXISTS tags (
    name VARCHAR(100) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
