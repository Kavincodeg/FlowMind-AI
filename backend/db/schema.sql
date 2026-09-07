-- ============================================================
-- FlowMind AI — Database Schema (Phase 1: Retrieval Foundation)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- documents: one row per ingested source document
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    doc_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50)  NOT NULL CHECK (source_type IN ('ticket', 'policy')),
    source_id   VARCHAR(200) NOT NULL,
    title       TEXT,
    metadata    JSONB        NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
CREATE INDEX IF NOT EXISTS idx_documents_metadata    ON documents USING gin(metadata);

-- ============================================================
-- chunks: one row per text chunk (unit of retrieval + citation)
-- ============================================================
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id    UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id      UUID    NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content     TEXT    NOT NULL,
    token_count INTEGER,
    char_offset INTEGER,
    embedding   vector(384),
    metadata    JSONB   NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (doc_id, chunk_index)
);

-- HNSW index for ANN cosine search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON chunks USING gin(metadata);

-- ============================================================
-- audit_log: Phase 6 placeholder
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    log_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID,
    step        VARCHAR(100),
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
