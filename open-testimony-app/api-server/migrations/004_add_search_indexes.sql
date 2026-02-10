-- Migration 004: Add search indexes for filtering and text search
-- Run with: psql -U postgres -d testimony -f migrations/004_add_search_indexes.sql

-- GIN index on incident_tags array for tag filtering (@> operator)
CREATE INDEX IF NOT EXISTS idx_videos_incident_tags ON videos USING GIN (incident_tags);

-- B-tree indexes for exact-match filters
CREATE INDEX IF NOT EXISTS idx_videos_category ON videos (category);
CREATE INDEX IF NOT EXISTS idx_videos_media_type ON videos (media_type);
CREATE INDEX IF NOT EXISTS idx_videos_source ON videos (source);

-- Enable pg_trgm for ILIKE trigram indexes
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Trigram GIN indexes for fast ILIKE text search
CREATE INDEX IF NOT EXISTS idx_videos_notes_trgm ON videos USING GIN (notes gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_videos_location_desc_trgm ON videos USING GIN (location_description gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_videos_device_id_trgm ON videos USING GIN (device_id gin_trgm_ops);
