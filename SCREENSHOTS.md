# Screenshots & Demo Clips

Capture these into `docs/screenshots/` and link them from the README. The goal is a
reviewer understanding the system in under a minute without running it. Suggested filenames
are listed so links stay stable.

## Stills

| # | File | What to capture | Why it matters |
|---|---|---|---|
| 1 | `architecture.png` | The rendered Mermaid diagram from the README | One-glance system overview |
| 2 | `swagger.png` | `http://localhost:8088/docs` showing `/ingest /search /answer /extract` | Proves the API surface is real and typed |
| 3 | `answer-cited.png` | A `/answer` response (Swagger "Try it out" or terminal) with `citations` + `confidence` | RAG with evidence, not vibes |
| 4 | `answer-lowconf.png` | An off-topic `/answer` showing `low_confidence: true` | The human-in-the-loop trigger |
| 5 | `extract-invoice.png` | `/extract` on `clean_invoice.pdf` → structured JSON | Document automation working end-to-end |
| 6 | `invoices-row.png` | `psql` (or a DB GUI) showing the persisted `app.invoices` row | Data actually lands, validated |
| 7 | `n8n-triage-canvas.png` | The Inbound Triage Agent workflow open in the n8n editor | The agent → switch → routing visual |
| 8 | `n8n-rag-canvas.png` | The RAG Support Agent canvas, If-node branches visible | Shows the escalation fork |
| 9 | `n8n-report-canvas.png` | The Ops Daily Report canvas | Schedule → queries → AI → Slack/Gmail |
| 10 | `slack-escalation.png` | A low-confidence escalation posted in `#ops` | Notification + HITL in the real channel |
| 11 | `slack-daily-report.png` | The daily report message in Slack | Reporting automation output |

## Short clips (Loom / GIF, 30–60s each)

| # | File | Flow to record |
|---|---|---|
| A | `demo-triage.mp4` | `curl` the inbound webhook with a lead message → show the new row appear in `app.leads` |
| B | `demo-rag.mp4` | Ask an in-domain question (cited answer) then an off-topic one (escalates to Slack + ticket) — the core story |
| C | `demo-report.mp4` | Run **Execute Workflow** on the daily report → summary posts to Slack |

## Tips
- Seed first (`make seed`) and run the triage webhook a few times so reports/tables aren't empty.
- Use a throwaway Slack workspace and a test Gmail address; blur any real emails/tokens.
- Clip B is the single most important asset — it shows automation *and* the judgment to escalate.
- Keep the terminal font large; crop browser chrome out of the n8n canvas shots.

> `docs/screenshots/` currently holds only `.gitkeep`. Generated images are gitignored by
> pattern except `.gitkeep` — adjust [`.gitignore`](.gitignore) if you want to commit them.
