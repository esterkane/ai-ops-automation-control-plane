---
name: scaffold-infra
description: Scaffold or repair the ai-ops-automation-control-plane Docker stack — n8n, Postgres 16 + pgvector, and the FastAPI "tools" microservice — plus .env, Makefile, and DB init. Use when setting up the project from scratch, adding/fixing a service in docker-compose, changing the Postgres schema bootstrap, or verifying the stack boots. (Prompt 1.)
---

# Scaffold & infra (Prompt 1)

Goal: a self-hosted AI workflow automation suite that boots with one command.

## Services (docker-compose.yml)
- **n8n** (`n8nio/n8n:latest`): basic auth on, persistent named volume `n8n_data`,
  `N8N_PORT=5678`, and **uses Postgres for its own storage in a separate `n8n`
  schema** (`DB_TYPE=postgresdb`, `DB_POSTGRESDB_SCHEMA=n8n`). Mount `./workflows`
  read-only so workflow JSON can be imported.
- **postgres** (`pgvector/pgvector:pg16`): named volume `postgres_data`, init scripts
  from `./postgres/init`, healthcheck via `pg_isready`. Bind only to `127.0.0.1` locally.
- **tools** (build `./tools`): FastAPI service on `8000`, `depends_on` postgres healthy.

## Postgres init (postgres/init/01-init.sql)
Enable `vector` + `pg_trgm`. Create:
- schemas `app` and `n8n`;
- `app.documents` — `vector(1536)` embedding column, `content_tsv tsvector` (maintained
  by trigger) for the full-text half of hybrid search, unique `(source, chunk_index)`,
  ivfflat + GIN indexes;
- `app.leads`, `app.tickets`, `app.invoices` (invoices holds the /extract output).

## Files to produce
- `docker-compose.yml`, `Makefile` (`up`/`down`/`logs`/`seed`/`test`/`fmt`)
- `.env.example` (every var: OPENAI/ANTHROPIC keys, DB creds, n8n auth, Slack/Gmail) and a
  real `.env` that is **gitignored** (never commit secrets — use `env_file:` in compose).
- `tools/`: `Dockerfile`, `pyproject.toml`, `app/main.py` (just `/health`),
  `app/config.py` (pydantic-settings), **empty stub modules** `app/embeddings.py` and
  `app/extraction.py` (raise `NotImplementedError`, filled by Prompts 2 & 3), and a
  `tests/test_health.py`.
- `README.md` skeleton with an **architecture section + diagram placeholder**.

## Rules
- No hardcoded secrets in `docker-compose.yml`; use `env_file: .env`.
- Do not expose internal ports publicly in a production profile (Postgres bound to localhost).
- FastAPI routes return typed Pydantic response models, never raw dicts.

## Verify & report
Boot the stack and confirm, then document the exact local URLs (n8n 5678, tools 8088→8000 + `/docs`,
postgres 55432→5432). End the response with the standard verification block:

```
Files changed:
- path  (added|modified|deleted)

Commands run:
- docker compose config        -> exit code
- docker compose up -d --build -> services healthy?
- curl http://localhost:8088/health -> 200 + body

Verification status:
- compose config: PASS / FAIL
- stack boots:    PASS / FAIL
- /health 200:    PASS / FAIL
- pytest:         PASS / FAIL
```
