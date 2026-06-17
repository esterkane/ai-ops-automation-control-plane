# Ops Daily Report

A scheduled agent that turns the last 24 hours of operational data into a plain-English
briefing and pushes it to Slack and email — no one has to open a dashboard.

## Trigger
- **Every Day 08:00** (`scheduleTrigger`) — runs daily at 08:00 in the instance timezone
  (`GENERIC_TIMEZONE` / `TZ` in `.env`).

## Data flow
```
Every Day 08:00
      │
      ▼
Query: Leads (24h)    (Postgres)  ── new_leads
      ▼
Query: Tickets (24h)  (Postgres)  ── new_tickets, open_tickets, high_priority
      ▼
Query: Invoices (24h) (Postgres)  ── new_invoices, invoice_total, needs_review
      ▼
Assemble Metrics (Code) ── collects all three result sets into one JSON object
      ▼
Summary Writer ◀── OpenAI Chat Model (ai_languageModel)
      │   (writes a <150-word leadership summary; told not to invent numbers)
      ├─▶ Post Report (Slack)   #ops
      └─▶ Email Report (Gmail)  ops@example.com
```

The three query nodes run in sequence; `Assemble Metrics` reads each one back by name
(`$('Query: Leads (24h)').first().json`, etc.) so the agent sees all metrics at once.

## Nodes
| Node | Type | Notes |
|---|---|---|
| Every Day 08:00 | `scheduleTrigger` | Daily at 08:00. |
| Query: Leads/Tickets/Invoices (24h) | `postgres` (executeQuery) | Read-only aggregates over `app.*`, 24h window. |
| Assemble Metrics | `code` | Merges the three result sets. |
| Summary Writer | `langchain.agent` | Plain-English report; grounded strictly in the metrics. |
| OpenAI Chat Model | `langchain.lmChatOpenAi` | `gpt-4o-mini`, temp 0.2. |
| Post Report (Slack) | `slack` | Posts to `#ops`. |
| Email Report (Gmail) | `gmail` | Sends to the configured address. |

## Credentials
- **SupportBrain Postgres** (`postgres`)
- **OpenAI account** (`openAiApi`)
- **Slack account** (`slackApi`)
- **Gmail account** (`gmailOAuth2`)

## Test it
Use **Execute Workflow** in the n8n editor to run it on demand without waiting for 08:00.
Seed some data first (run the triage workflow a few times, or `make seed`) so the
aggregates are non-zero.
