# RAG Support Agent

Answers support questions from the internal knowledge base with citations — and,
crucially, **escalates to a human when the retrieval evidence is weak** instead of
guessing. This is the human-in-the-loop centrepiece.

## Trigger
- **Webhook: Support Chat** (`POST /webhook/support`) — JSON body with `query`
  (or `text`). Uses `responseMode: responseNode`, so a Respond node returns the reply.

## Data flow
```
Webhook: Support Chat
      │
      ▼
Call /answer (RAG)  ── HTTP POST tools:8000/answer  {query, top_k:5}
      │   returns { answer, citations, low_confidence, confidence }
      ▼
Low confidence?  (If — checks $json.low_confidence)
   ├─ true  ─▶ Escalate to Slack (#ops)         ─▶ Respond: Escalated
   │          Create Escalation Ticket (Postgres, priority=high)
   └─ false ─▶ Respond: Cited Answer  (answer + citations + confidence)
```

## Why this matters
The FastAPI `/answer` endpoint sets `low_confidence: true` when the best supporting
evidence falls below `RAG_LOW_CONFIDENCE_THRESHOLD`. The workflow trusts that single
flag to decide between **auto-reply** and **human escalation** — the boundary between
automation and oversight lives in code, not in a brittle prompt.

## Nodes
| Node | Type | Notes |
|---|---|---|
| Webhook: Support Chat | `webhook` | `responseMode: responseNode`. |
| Call /answer (RAG) | `httpRequest` | POSTs JSON to the tools service. |
| Low confidence? | `if` (v2) | Boolean check on `low_confidence`. |
| Escalate to Slack | `slack` | Posts the question + draft answer to `#ops`. |
| Create Escalation Ticket | `postgres` (insert) | High-priority ticket into `app.tickets`. |
| Respond: Escalated / Cited Answer | `respondToWebhook` | One reply per branch. |

## Credentials
- **SupportBrain Postgres** (`postgres`)
- **Slack account** (`slackApi`)
- (`/answer` itself calls the LLM provider configured in the tools service `.env` —
  no n8n LLM credential is needed for this workflow.)

## Test it
```bash
# In-domain question (seed the KB first: `make seed`)
curl -s -X POST http://localhost:5678/webhook/support \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the refund window for monthly plans?"}'
# → cited answer returned directly

# Off-topic question
curl -s -X POST http://localhost:5678/webhook/support \
  -H "Content-Type: application/json" \
  -d '{"query":"Who won the 1998 world cup?"}'
# → low confidence → posted to #ops + ticket created → "escalated" response
```
