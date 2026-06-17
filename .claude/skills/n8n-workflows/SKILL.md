---
name: n8n-workflows
description: Author the three importable n8n workflow JSON files (inbound-triage-agent, rag-support-agent, ops-daily-report) under /workflows, each with a markdown doc, wiring n8n AI Agent / Switch / HTTP Request / Postgres / Slack / Gmail nodes to the FastAPI tools service. Use when creating, editing, or documenting n8n workflows, agent routing, or scheduled report automation in this repo. (Prompt 4.)
---

# n8n workflows as code (Prompt 4)

Write each workflow as an **importable n8n JSON file** in `/workflows/` (importable via the
n8n UI or `n8n import:workflow --input=...`). For each, write a markdown doc explaining nodes,
triggers, and data flow. Keep custom logic in the FastAPI service — call it via **HTTP Request**
nodes (`http://tools:8000/...` inside the compose network).

## 1. `inbound-triage-agent.json`
Webhook/Email trigger → **AI Agent** node (Anthropic or OpenAI model) that classifies the
message as `lead | support | invoice | hr` and extracts fields → **Switch** routing to:
- `lead`   → Postgres insert into `app.leads`
- `support`→ Postgres insert into `app.tickets`
- `invoice`→ HTTP Request to `/extract`
- `hr`     → Slack notify the HR channel

## 2. `rag-support-agent.json`
Chat/Webhook trigger → **HTTP Request** to `/answer` → **If** node on the `low_confidence` flag:
- low confidence → escalate: Slack post to support channel **and** Postgres insert a ticket
- else → reply with the cited answer.

## 3. `ops-daily-report.json`
**Schedule** trigger (daily) → Postgres query nodes aggregating leads / tickets / invoices from
the last 24h → **AI Agent** node writing a plain-English summary → Slack post **and** Gmail send.

## Deliverables
- Three valid workflow JSON files (correct n8n shape: `nodes`, `connections`, `settings`).
- A `.md` doc per workflow (nodes, triggers, data flow, sample payloads).
- `/workflows/README.md`: how to import all three + which **credentials** each needs
  (Postgres, Slack, Gmail, OpenAI/Anthropic, the tools service base URL).

## Notes
- Reference credentials by name; do not embed secrets in the JSON.
- Make webhooks testable (document the test URL and an example curl payload).
