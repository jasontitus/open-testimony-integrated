-- Migration 001: Add annotation fields to videos table and crypto_version to devices
-- Idempotent: safe to run multiple times

ALTER TABLE videos ADD COLUMN IF NOT EXISTS media_type VARCHAR(20) DEFAULT 'video';
ALTER TABLE videos ADD COLUMN IF NOT EXISTS exif_metadata JSONB;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS category VARCHAR(50);
ALTER TABLE videos ADD COLUMN IF NOT EXISTS location_description VARCHAR(500);
ALTER TABLE videos ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS annotations_updated_at TIMESTAMP;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS annotations_updated_by VARCHAR(255);

ALTER TABLE devices ADD COLUMN IF NOT EXISTS crypto_version VARCHAR(20) DEFAULT 'hmac';
