-- ===========================================================================
-- ai-ops-automation-control-plane :: database bootstrap
-- Runs once, on first container start, via docker-entrypoint-initdb.d.
-- ===========================================================================

-- pgvector for embedding similarity search.
CREATE EXTENSION IF NOT EXISTS vector;
-- pg_trgm helps fuzzy matching / trigram ranking on titles and bodies.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- Schemas: keep n8n's internal tables separate from application data.
-- n8n is pointed at the `n8n` schema via DB_POSTGRESDB_SCHEMA in compose.
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS n8n;

-- ---------------------------------------------------------------------------
-- documents: RAG knowledge base. One row per chunk.
-- vector(1536) matches OpenAI text-embedding-3-small / Anthropic-compatible
-- dimensionality. Change the column type if you swap embedding models.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.documents (
    id           BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source       TEXT        NOT NULL,
    title        TEXT        NOT NULL,
    chunk_index  INTEGER     NOT NULL DEFAULT 0,
    content      TEXT        NOT NULL,
    embedding    vector(1536),
    -- Full-text search vector kept in sync via trigger below.
    content_tsv  tsvector,
    metadata     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Keep one chunk per (source, chunk_index) so re-ingest can upsert cleanly.
CREATE UNIQUE INDEX IF NOT EXISTS documents_source_chunk_uq
    ON app.documents (source, chunk_index);

-- Approximate nearest-neighbour index for cosine distance.
CREATE INDEX IF NOT EXISTS documents_embedding_ivf
    ON app.documents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- GIN index backing the full-text side of hybrid retrieval.
CREATE INDEX IF NOT EXISTS documents_content_tsv_gin
    ON app.documents USING gin (content_tsv);

-- Trigger to maintain content_tsv on insert/update.
CREATE OR REPLACE FUNCTION app.documents_tsv_trigger() RETURNS trigger AS $$
BEGIN
    NEW.content_tsv :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.content, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS documents_tsv_update ON app.documents;
CREATE TRIGGER documents_tsv_update
    BEFORE INSERT OR UPDATE ON app.documents
    FOR EACH ROW EXECUTE FUNCTION app.documents_tsv_trigger();

-- ---------------------------------------------------------------------------
-- leads: captured from inbound triage (sales-ish messages).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.leads (
    id           BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         TEXT,
    email        TEXT,
    company      TEXT,
    message      TEXT,
    source       TEXT,
    status       TEXT        NOT NULL DEFAULT 'new',
    metadata     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- tickets: support requests + human-in-the-loop escalations.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.tickets (
    id           BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject      TEXT        NOT NULL,
    body         TEXT,
    requester    TEXT,
    channel      TEXT,
    priority     TEXT        NOT NULL DEFAULT 'normal',
    status       TEXT        NOT NULL DEFAULT 'open',
    metadata     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- invoices: structured output of the /extract document pipeline.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.invoices (
    id              BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vendor          TEXT,
    invoice_number  TEXT,
    invoice_date    DATE,
    due_date        DATE,
    currency        TEXT,
    total           NUMERIC(14, 2),
    line_items      JSONB       NOT NULL DEFAULT '[]'::jsonb,
    source_file     TEXT,
    low_confidence  BOOLEAN     NOT NULL DEFAULT false,
    raw_extraction  JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS invoices_vendor_idx ON app.invoices (vendor);
CREATE UNIQUE INDEX IF NOT EXISTS invoices_vendor_number_uq
    ON app.invoices (vendor, invoice_number)
    WHERE invoice_number IS NOT NULL;
