---
name: rag-knowledge-base
description: Implement the internal-knowledge-base RAG pipeline in the FastAPI tools service — /ingest (chunk + embed + upsert to pgvector), /search (hybrid pgvector cosine + Postgres full-text with reciprocal rank fusion), and /answer (grounded answer with citations and a low-confidence escalation flag), plus seed handbook/FAQ data and pytest. Use for any RAG, embeddings, hybrid retrieval, citations, or knowledge-base work in this repo. (Prompt 2.)
---

# RAG knowledge base (Prompt 2)

Build evidence-first retrieval in `tools/app/`. Lean on retrieval quality, not guessing.

## Endpoints
1. **POST `/ingest`** — accepts documents (text or PDF; reuse `extraction.extract_text_from_pdf`
   for PDFs once Prompt 3 lands, else a local pypdf read). Chunk (token/char window with overlap),
   generate embeddings (configurable: OpenAI `text-embedding-3-small` or Anthropic-compatible via
   `EMBEDDING_PROVIDER`), and **upsert** into `app.documents` with metadata
   (`source`, `title`, `chunk_index`). Upsert on the `(source, chunk_index)` unique key.
2. **POST `/search`** — **hybrid retrieval**:
   - vector: `embedding <=> query_vec` cosine distance (pgvector);
   - lexical: `content_tsv @@ websearch_to_tsquery('english', q)` ranked by `ts_rank_cd`;
   - combine with **reciprocal rank fusion** (`score = Σ 1/(k + rank)`, k≈60).
   Return top-k chunks with fused scores + evidence snippets.
3. **POST `/answer`** — run `/search`, then ask the LLM (via `LLM_PROVIDER`/`LLM_MODEL`) to answer
   **only from retrieved context**. Return `answer` + `citations` (source, chunk_id, score).
   Set `low_confidence: true` when top fused scores fall below
   `RAG_LOW_CONFIDENCE_THRESHOLD` — this is the human-in-the-loop signal n8n routes on.

## Implementation notes
- Fill in `app/embeddings.py` (`embed_texts`) honoring `EMBEDDING_DIM` (must match `vector(1536)`).
- Add `app/rag.py` (chunking, RRF, retrieval) and `app/db.py` (psycopg + pgvector registration).
- Pydantic models throughout; proper error handling; routes return typed response models.
- **Citations are mandatory** in every `/answer` response.

## Seed data
Populate `app/seed.py` (run by `make seed`) with a fake **company handbook** + **product FAQ**
so the suite is demoable out of the box. Ingest them through the real `/ingest` path.

## Tests (tools/tests/)
Pytest suite with a **fixture knowledge base**. Stub/patch the embedding + LLM calls so tests are
fast and deterministic. Cover: ingest→search retrieves the right chunk; RRF ordering; `/answer`
emits citations; weak retrieval sets `low_confidence`.

## Verify & report
End with the standard verification block (pytest / ruff / mypy / manual smoke of /ingest→/answer).
