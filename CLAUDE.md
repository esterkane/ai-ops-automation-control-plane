# CLAUDE.md — ai-ops-automation-control-plane

Self-hosted AI workflow automation suite: **n8n** (visual orchestration) + a
**FastAPI "tools" microservice** (RAG over an internal knowledge base, document
extraction, embeddings), backed by **Postgres 16 + pgvector**. On-prem via Docker
Compose. The project self-describes as **complete** (Prompts 1–5). See
`README.md`, `CASE-STUDY.md`, `SECURITY.md`.

## Architecture in 5 lines
1. `n8n` (:5678) orchestrates AI-agent workflows and calls the tools service over HTTP.
2. `tools` (FastAPI, container :8000 → host :8088) exposes `/ingest`, `/search`, `/answer`, `/extract`.
3. `postgres` (pgvector/pg16, container :5432 → host :55432) holds the `app` schema (docs/leads/tickets/invoices) and the `n8n` schema (n8n state).
4. Retrieval is **hybrid**: pgvector cosine + Postgres full-text, fused with reciprocal rank fusion (`tools/app/rag.py`, `tools/app/db.py`).
5. LLM/embeddings are provider-agnostic (`tools/app/llm.py`, `tools/app/embeddings.py`): OpenAI/Anthropic when keyed, otherwise a deterministic local embedding + extractive answerer (offline by default).

## Run / test commands
All backend work happens in `tools/`. The Makefile drives the stack; CI runs the
same lint/type/test against a real Postgres.

| Purpose | Command |
|---|---|
| Start stack | `cp .env.example .env` then `make up` (needs `.env`; runs `docker compose up --build -d`) |
| Logs / status / stop | `make logs` · `make ps` · `make down` |
| Seed demo KB | `make seed` (`docker compose exec tools python -m app.seed`) |
| Tests | `make test` (`docker compose exec tools pytest -q`); local: `cd tools && pytest -q` |
| Lint | `cd tools && ruff check .` (or `make fmt`) |
| Type-check | `cd tools && mypy app` (`mypy --strict`, configured in `pyproject.toml`) |
| Quality gate (CI) | `.github/workflows/ci.yml` on push/PR to `main`: bootstrap `postgres/init/01-init.sql` → `pip install -e ".[dev]"` → `ruff check .` → `mypy app` → `pytest -q`, with a live `pgvector/pgvector:pg16` service and `EMBEDDING_PROVIDER=local`, `LLM_PROVIDER=local`. |

Local-without-Docker setup: `cd tools && pip install -e ".[dev]"`; tests need a
reachable Postgres (`DATABASE_URL`) — integration tests do **not** mock the DB.

## External services & how config/secrets load
- **Postgres 16 + pgvector** — metadata + RAG vector store (`app` schema) and n8n
  state (`n8n` schema). Schema bootstrapped by `postgres/init/01-init.sql`.
- **n8n** — workflow orchestration / AI-agent nodes; persists to the `n8n` schema.
- **LLM provider** — OpenAI or Anthropic (`LLM_PROVIDER`, `LLM_MODEL`); `local`
  fallback when keys are placeholders/unset.
- **Embeddings** — OpenAI `text-embedding-3-small` (dim 1536) or the deterministic
  `local` hashing embedding.
- **Integrations (n8n credentials, not the tools service)** — Slack (`#ops`/`#hr`)
  and Gmail.

Config/secrets: `tools/app/config.py` uses **pydantic-settings** reading
`.env` / process env. Compose injects secrets via `env_file: .env` per service.
`.env` is gitignored; `.env.example` documents every variable. No secrets are
hardcoded in `docker-compose.yml`. Postgres is bound to `127.0.0.1` only.

## Invariants I must never break
1. **Determinism of the pipeline.** The `local` embedding (`tools/app/embeddings.py`) and reciprocal-rank-fusion / chunking helpers (`tools/app/rag.py`) are deterministic — keep them so. The CI quality gate runs with `EMBEDDING_PROVIDER=local`/`LLM_PROVIDER=local`, so non-deterministic behavior breaks tests.
2. **Quality gates pass.** `ruff check .`, `mypy app` (strict), and `pytest -q` must all pass. No `# type: ignore` without an explanatory comment; honor the strict config in `pyproject.toml`.
3. **Provenance on every chunk / grounded answers.** `/answer` answers **only** from retrieved context and returns citations (`source`, `chunk_id`, `score`) plus a `low_confidence` flag. Do not return ungrounded answers or strip citations.
4. **No secrets in git.** Secrets live in `.env` (gitignored); document new vars in `.env.example`; pass them via `env_file:`. Never hardcode keys/passwords.

Repo-specific invariants found here:
- **Hybrid-only retrieval.** `/search` must fuse pgvector cosine + Postgres full-text via RRF — not vector-only or lexical-only.
- **Idempotent ingest.** Re-ingesting a `source` deletes its existing chunks first (`tools/app/db.py`); keep ingest idempotent per `source`. Invoice upserts (`app.invoices`) are likewise conflict-safe.
- **Human-in-the-loop gate.** `low_confidence` (RAG below `RAG_LOW_CONFIDENCE_THRESHOLD`; non-invoice docs in `/extract`) must escalate, not guess. Low-confidence extractions are **not** persisted (no garbage rows).
- **Pinned infra.** Postgres is `pgvector/pgvector:pg16` and `EMBEDDING_DIM` must match the `documents.embedding` column (1536).

## Definition of done
- [ ] `pytest -q` passes (`make test` / `cd tools && pytest -q`).
- [ ] `mypy app` passes (strict) — type-checker exists; not N/A.
- [ ] `ruff check .` passes.
- [ ] CI quality gate green (`.github/workflows/ci.yml`).
- [ ] Provenance/grounding intact: `/answer` keeps citations + `low_confidence`; `/search` stays hybrid.
- [ ] README / relevant docs updated for behavior or config changes.
- [ ] No secrets added; new env vars documented in `.env.example`.
