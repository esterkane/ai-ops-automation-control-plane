# Inbound Triage Agent

Classifies any inbound message (email, web form, chat) and routes it to the right
place — turning an unstructured message into a lead, a ticket, an invoice
extraction, or an HR notification, with no human triage step.

## Trigger
- **Webhook: Inbound** (`POST /webhook/inbound`) — accepts a JSON body. The agent
  reads `body.message`, falling back to `body.text`, then the whole body.

## Data flow
```
Webhook: Inbound
      │
      ▼
Classifier Agent ◀── OpenAI Chat Model (ai_languageModel)
      │   (returns JSON: category + extracted fields)
      ▼
Parse Classification (Code) ── validates JSON, defaults unknown → "support"
      │   sets $json.category and $json.classification
      ▼
Route by Category (Switch)
   ├─ lead    ─▶ Insert Lead        (Postgres → app.leads)
   ├─ support ─▶ Create Ticket      (Postgres → app.tickets)
   ├─ invoice ─▶ Call /extract      (HTTP → tools:8000/extract, binary "file")
   └─ hr      ─▶ Notify HR (Slack)  (#hr channel)
```

## Nodes
| Node | Type | Notes |
|---|---|---|
| Webhook: Inbound | `webhook` | `responseMode: lastNode`. |
| Classifier Agent | `langchain.agent` | System prompt forces a strict JSON classification. |
| OpenAI Chat Model | `langchain.lmChatOpenAi` | `gpt-4o-mini`, temp 0. Swap for `lmChatAnthropic` if preferred. |
| Parse Classification | `code` | `JSON.parse` the agent output; guards against malformed output. |
| Route by Category | `switch` (v3) | Four string-equals rules → four outputs. |
| Insert Lead / Create Ticket | `postgres` (insert) | Parameterised column mapping into the `app` schema. |
| Call /extract | `httpRequest` | Forwards the incoming binary (`data`) as multipart `file`. |
| Notify HR (Slack) | `slack` | Posts to `#hr`. |

## Credentials
- **SupportBrain Postgres** (`postgres`)
- **OpenAI account** (`openAiApi`)
- **Slack account** (`slackApi`)

## Test it
```bash
curl -s -X POST http://localhost:5678/webhook/inbound \
  -H "Content-Type: application/json" \
  -d '{"message":"Hi, I am Dana from Globex and we want a quote for 200 units."}'
# → classified as "lead", row inserted into app.leads
```
The invoice branch expects a binary PDF on the incoming item (field `data`); send a
`multipart/form-data` request with the file attached when testing that path.
