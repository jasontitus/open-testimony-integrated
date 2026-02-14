-- Migration 008: Add clip and action embedding tables for video understanding
--
-- clip_embeddings: mean-pooled vision embeddings across overlapping temporal windows
--   Captures what a clip window LOOKS like across time (motion, pose changes)
--   Searched with vision model text encoding (same as frame_embeddings)
--
-- action_embeddings: text embeddings of temporal action captions from multi-frame analysis
--   Captures described ACTIONS happening across time (chokehold, pushing, use of force)
--   Searched with text model encoding (same as caption_embeddings)
--
-- Both tables use overlapping sliding windows (default: 16 frames at 4fps = 4s windows,
-- stride 8 frames = 50% overlap) to ensure no action falls between window boundaries.

-- Clip embeddings (vision model dimension, same as frame_embeddings)
CREATE TABLE IF NOT EXISTS clip_embeddings (
    id BIGSERIAL PRIMARY KEY,
    video_id UUID NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    start_frame INTEGER NOT NULL,
    end_frame INTEGER NOT NULL,
    num_frames INTEGER NOT NULL,
    embedding vector(1152),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_clip_embeddings_video_id ON clip_embeddings (video_id);
CREATE INDEX IF NOT EXISTS clip_emb_hnsw ON clip_embeddings USING hnsw (embedding vector_cosine_ops);

-- Action embeddings (text model dimension, same as transcript/caption_embeddings)
CREATE TABLE IF NOT EXISTS action_embeddings (
    id BIGSERIAL PRIMARY KEY,
    video_id UUID NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    start_frame INTEGER NOT NULL,
    end_frame INTEGER NOT NULL,
    num_frames INTEGER NOT NULL,
    action_text TEXT NOT NULL,
    embedding vector(4096),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_action_embeddings_video_id ON action_embeddings (video_id);
CREATE INDEX IF NOT EXISTS action_emb_hnsw ON action_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS ix_action_text_trgm ON action_embeddings USING gin (action_text gin_trgm_ops);

-- Add clip tracking columns to video_index_status
ALTER TABLE video_index_status ADD COLUMN IF NOT EXISTS clip_indexed BOOLEAN DEFAULT false;
ALTER TABLE video_index_status ADD COLUMN IF NOT EXISTS clip_count INTEGER;
