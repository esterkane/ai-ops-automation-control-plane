# Security & Operations

This is a self-hosted reference implementation. The notes below cover how secrets are
handled today, the database posture, and what changes for a real production deployment.

## Secrets

- **Nothing secret is committed.** `.env` is gitignored; [`.env.example`](.env.example)
  documents every variable with placeholder values. The repo ships only placeholders.
- **Compose reads secrets via `env_file:`**, never inline literals in
  [`docker-compose.yml`](docker-compose.yml). No key, token, or password appears in the
  compose file itself.
- **n8n workflows reference credentials by name**, not value — the exported JSON in
  `workflows/` contains credential *names* (`SupportBrain Postgres`, `OpenAI account`, …),
  and the actual secrets live in n8n's encrypted credential store.
- **LLM keys** (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) are read only by the FastAPI tools
  service from its environment. With placeholder keys the service runs fully offline.

### For production
- Move secrets out of a flat `.env` into **Docker secrets** or a manager (Vault, AWS/GCP
  secret manager, SOPS-encrypted files). Mount them as files, not environment where possible.
- Set a strong, persisted **`N8N_ENCRYPTION_KEY`** so the credential store survives restarts
  and can't be silently re-keyed.
- Rotate the n8n basic-auth password and the Postgres password from the demo defaults.

## Database posture

- **Two schemas, one database.** Application data lives in `app`; n8n's own tables live in
  `n8n` (`DB_POSTGRESDB_SCHEMA=n8n`). They share a database but are logically separated.
- **Postgres is bound to localhost only** (`127.0.0.1:55432`) for local inspection — it is
  not published on a public interface. The `tools` and `n8n` containers reach it over the
  internal compose network on `5432`.
- **User input that reaches SQL is parameterised.** The tools service uses psycopg with bound
  parameters (`%s`, `::vector` / `::jsonb` casts), and the n8n Postgres nodes use the node's
  parameterised insert mapping rather than string-built queries.

### For production: least-privilege roles
The demo uses one superuser-ish role for simplicity. Split it:

```sql
-- App role: read/write app data only, no DDL, no n8n schema.
CREATE ROLE aiops_app LOGIN PASSWORD '...';
GRANT USAGE ON SCHEMA app TO aiops_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO aiops_app;

-- n8n role: owns only the n8n schema (it manages its own DDL/migrations).
CREATE ROLE aiops_n8n LOGIN PASSWORD '...';
GRANT ALL ON SCHEMA n8n TO aiops_n8n;
```
Point the tools service at `aiops_app` and n8n at `aiops_n8n`. Neither can touch the other's
schema, and a compromised tools service cannot alter schema or read n8n credentials' tables.

## Network & exposure

- Only the ports you actually need should be published. For production, expose **n8n behind a
  reverse proxy with TLS** (the webhook URLs become `https://…`), and do **not** publish the
  tools service or Postgres beyond the internal network.
- Set `WEBHOOK_URL` to the public HTTPS origin so n8n generates correct callback URLs.

## Dependencies

- Pin and audit: run `pip-audit` (Python) and `npm audit` against any added JS tooling in CI;
  block merges that introduce known CVEs.

## Scaling n8n for production (queue mode + Redis)

The default ("regular") mode runs triggers and executions in one process — fine for this
demo, a bottleneck under load. Production n8n uses **queue mode**: a main process enqueues
executions to **Redis**, and a pool of **workers** consumes them. Webhooks can be handled by
dedicated webhook processes so ingestion isn't blocked by long-running executions.

```
                       ┌────────────┐
  webhook/UI  ───────▶ │  n8n main  │ ──enqueue──▶ Redis ──▶ ┌─ n8n worker 1 ─┐
                       │ (+ webhook │                        ├─ n8n worker 2 ─┤ ──▶ Postgres
                       │  processes)│ ◀──results/state──────  └─ n8n worker N ─┘
                       └────────────┘
                              │
                         Postgres (n8n schema, externalised)
```

What changes:
- `EXECUTIONS_MODE=queue` and a reachable **Redis** (`QUEUE_BULL_REDIS_HOST=redis`).
- Run the **same image** with the `worker` command as a separately scaled service
  (`docker compose up --scale n8n-worker=N`, or replicas in Kubernetes).
- Keep Postgres as the shared state store, ideally **externalised** (managed Postgres) rather
  than a compose-local container, with backups.
- A persisted `N8N_ENCRYPTION_KEY` shared across main + workers so they can all decrypt
  credentials.

Sketch of the extra compose services:

```yaml
  redis:
    image: redis:7
    restart: unless-stopped

  n8n-worker:
    image: n8nio/n8n:latest
    command: worker
    env_file: .env
    environment:
      EXECUTIONS_MODE: queue
      QUEUE_BULL_REDIS_HOST: redis
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_SCHEMA: n8n
    depends_on: [redis, postgres]
    deploy:
      replicas: 3
```
(The main `n8n` service gets the same `EXECUTIONS_MODE`/`QUEUE_BULL_REDIS_HOST` settings.)

## Reporting a vulnerability

This is a portfolio/reference project. If you spot a security issue, open an issue (omit
exploit details for anything sensitive) or contact the repository owner.
