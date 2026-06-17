# n8n Workflows

Three importable workflows that orchestrate the suite. The custom AI logic lives in the
FastAPI `tools` service; these workflows call it over HTTP and handle routing,
persistence, notifications, and scheduling.

| Workflow | Trigger | What it does | Doc |
|---|---|---|---|
| [`inbound-triage-agent.json`](inbound-triage-agent.json) | Webhook `POST /webhook/inbound` | Classify a message (lead/support/invoice/hr) and route it. | [doc](inbound-triage-agent.md) |
| [`rag-support-agent.json`](rag-support-agent.json) | Webhook `POST /webhook/support` | Cited RAG answer; escalate to a human when confidence is low. | [doc](rag-support-agent.md) |
| [`ops-daily-report.json`](ops-daily-report.json) | Schedule (daily 08:00) | Aggregate 24h ops data → AI summary → Slack + Gmail. | [doc](ops-daily-report.md) |

## Importing

### Via the n8n CLI (Docker)
The compose stack mounts this directory read-only at `/workflows` inside the n8n container.

```bash
# Import all three at once
docker compose exec n8n n8n import:workflow --separate --input=/workflows

# …or one at a time
docker compose exec n8n n8n import:workflow --input=/workflows/rag-support-agent.json
```
> On Git Bash / MSYS (Windows), prefix with `MSYS_NO_PATHCONV=1` so `/workflows` isn't
> rewritten to a Windows path.

### Via the n8n UI
Open http://localhost:5678 → **Workflows** → **Import from File** → pick a `*.json` file.

## After importing: connect credentials
Every workflow references credentials **by name** — no secrets are stored in the JSON.
Create these once under **Credentials** in the n8n UI, then open each workflow and confirm
each node points at them:

| Credential name | n8n type | Used by | Notes |
|---|---|---|---|
| SupportBrain Postgres | `postgres` | all three | Host `postgres`, port `5432`, db/user/password from `.env`. |
| OpenAI account | `openAiApi` | triage, daily report | API key. Or replace the model node with `lmChatAnthropic`. |
| Slack account | `slackApi` | all three | Bot token with `chat:write`; channels `#ops`, `#hr`. |
| Gmail account | `gmailOAuth2` | daily report | OAuth2 (or swap for an SMTP node). |

The HTTP Request nodes call `http://tools:8000/...` over the compose network — no credential
needed for the tools service itself.

## Activate
Workflows import **inactive** (`active: false`). Toggle **Active** in the editor to enable
the webhook/schedule triggers, or run **Execute Workflow** to test on demand.
