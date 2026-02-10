-- Migration 005: Add pgvector extension and AI search tables
-- Requires: pgvector/pgvector:pg16 Docker image (drop-in replacement for postgres:16)

CREATE EXTENSION IF NOT EXISTS vector;

-- Visual search embeddings (one row per extracted video frame)
CREATE TABLE frame_embeddings (
    id            BIGSERIAL PRIMARY KEY,
    video_id      UUID NOT NULL REFERENCES videos(id),
    frame_num     INTEGER NOT NULL,
    timestamp_ms  INTEGER NOT NULL,
    embedding     vector(768),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX frame_emb_hnsw ON frame_embeddings
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX frame_emb_video ON frame_embeddings (video_id);

-- Transcript embeddings (one row per spoken segment)
CREATE TABLE transcript_embeddings (
    id            BIGSERIAL PRIMARY KEY,
    video_id      UUID NOT NULL REFERENCES videos(id),
    segment_text  TEXT NOT NULL,
    start_ms      INTEGER NOT NULL,
    end_ms        INTEGER NOT NULL,
    embedding     vector(4096),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX transcript_emb_hnsw ON transcript_embeddings
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX transcript_emb_video ON transcript_embeddings (video_id);

-- Indexing job tracking (one row per video)
CREATE TABLE video_index_status (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id          UUID NOT NULL UNIQUE REFERENCES videos(id),
    object_name       VARCHAR(500) NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'pending',
    visual_indexed    BOOLEAN DEFAULT FALSE,
    transcript_indexed BOOLEAN DEFAULT FALSE,
    frame_count       INTEGER,
    segment_count     INTEGER,
    error_message     TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    completed_at      TIMESTAMPTZ
);
