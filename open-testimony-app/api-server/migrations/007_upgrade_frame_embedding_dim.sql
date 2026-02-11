-- Migration 007: Upgrade frame_embeddings vector dimension from 768 to 1280
-- Required when switching vision model from ViT-L-14 (768-dim) to ViT-bigG-14 (1280-dim).
-- Existing embeddings must be re-indexed after this migration.

-- Drop the HNSW index (cannot ALTER a vector column with an index on it)
DROP INDEX IF EXISTS frame_emb_hnsw;

-- Change the column type
ALTER TABLE frame_embeddings
    ALTER COLUMN embedding TYPE vector(1280);

-- Recreate the HNSW index
CREATE INDEX frame_emb_hnsw ON frame_embeddings
    USING hnsw (embedding vector_cosine_ops);
