# Case Study — Automating a Holding Company's Internal Ops

> This is a reference implementation, not a production deployment at a named company.
> The scenario and the "before" numbers are illustrative; the system, the workflows,
> and the code are real and run locally. Treat the outcomes as *what this design is
> built to achieve*, not as audited results.

## The setup

A small holding company runs several portfolio businesses from one back office. A
handful of people handle everything that lands in shared inboxes and forms: sales
enquiries, customer support questions, supplier invoices, and the occasional HR note.
Three things made that painful:

1. **Everything arrived in one undifferentiated stream.** A person read each message,
   decided what it was, and copied the relevant bits into the right system (CRM row,
   ticket, accounting sheet).
2. **Answering repeat support questions meant hunting through documents.** The answers
   existed — in a handbook, an FAQ, old tickets — but finding and quoting them took time,
   and answers drifted as people half-remembered policy.
3. **Nobody had a daily picture.** "How many leads yesterday? Any invoices that need a
   second look?" required opening three tools.

## Before

| Step | How it worked | Cost |
|---|---|---|
| Triage | Human reads each message, classifies, routes by hand | ~2–4 min/message, all day |
| Support answers | Human searches docs, writes answer, hopes it's current | Slow; inconsistent; no citations |
| Invoice entry | Human keys vendor / number / total into a sheet | Error-prone; no validation |
| Daily status | Someone compiles numbers manually, if at all | Often skipped |

The common thread: a person was the integration layer between systems, doing work that
is *structured* but was being done *manually*.

## After

The control plane puts a thin automation layer in front of that stream. n8n owns the
orchestration; a FastAPI service owns the AI logic; Postgres holds both the data and the
embeddings.

| Step | How it works now | What changed |
|---|---|---|
| Triage | [`inbound-triage-agent`](workflows/inbound-triage-agent.md): AI Agent classifies + extracts → Switch routes to lead / ticket / invoice / HR | The message lands in the right place with fields already parsed |
| Support answers | [`rag-support-agent`](workflows/rag-support-agent.md): hybrid RAG answer **with citations**; low-confidence questions escalate to a human | Consistent, sourced answers; humans only see the genuinely hard ones |
| Invoice entry | [`/extract`](tools/app/extraction.py): PDF → validated structured fields → `app.invoices`, with a review flag on anything uncertain | No manual keying; bad parses are flagged, not silently saved |
| Daily status | [`ops-daily-report`](workflows/ops-daily-report.md): scheduled aggregation → plain-English summary → Slack + email | The picture shows up every morning without anyone assembling it |

## Why it's trustworthy, not just fast

The interesting design choice is where the **human stays in the loop**. The RAG endpoint
returns a `low_confidence` flag whenever the retrieved evidence is weak, and the support
workflow routes on exactly that flag: strong evidence → cited auto-answer; weak evidence →
Slack escalation plus a ticket. The boundary between "the machine handles it" and "a person
should look" lives in code and is easy to tune (`RAG_LOW_CONFIDENCE_THRESHOLD`), rather than
being buried in a prompt and hoped for.

The same conservatism shows up in extraction: a document that doesn't parse cleanly as an
invoice is flagged and **not** written to the table, so automation never quietly produces a
wrong row.

## What it's built to move

| Metric | Direction | Why |
|---|---|---|
| Triage time per message | ↓ toward seconds | Classification + field extraction is automated |
| Manual touches per item | ↓ | Routing, ticket/lead creation, invoice entry happen without a person |
| Support answer consistency | ↑ | Answers are quoted from source documents with citations |
| Questions needing a human | ↓ to the hard ones only | Confidence-gated escalation filters the easy majority |
| "Do we have a daily picture?" | yes, daily | Scheduled report, no manual assembly |

## Honest limitations

- The offline mode uses a deterministic local embedding and an extractive answerer so the
  suite demos without API keys; semantic quality steps up materially with a real
  OpenAI/Anthropic key.
- The n8n workflows ship inactive and reference credentials by name — they need real Slack,
  Gmail, and LLM credentials connected before they do anything outward-facing.
- Invoice extraction is tuned and tested on a few document shapes; real-world invoices vary
  enormously and would need broader evaluation before trusting auto-persist.

## Skills this exercises

AI agents · LLM orchestration · RAG with citations · document automation · n8n workflow
automation · API integration · reporting automation · notifications · human-in-the-loop
design · self-hosted, security-conscious deployment. See the [README](README.md#what-this-demonstrates)
for the file-level map.
