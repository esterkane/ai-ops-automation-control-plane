---
name: portfolio-docs
description: Finalize the repo for a portfolio reviewer — a strong README with a Mermaid data-flow diagram and a "what this demonstrates" skills map, a concrete CASE-STUDY.md, a SECURITY.md (secrets, DB roles, n8n queue-mode scaling with Redis), and a docs/screenshots plan (SCREENSHOTS.md). Use when writing or polishing project documentation, the architecture diagram, the case study, or the security/scaling write-up. (Prompt 5.)
---

# Portfolio documentation (Prompt 5)

Polish the repo so a reviewer immediately understands what it is and what it demonstrates.

## README.md
- What the suite does; setup steps; local URLs.
- **Mermaid** data-flow diagram across n8n → FastAPI tools → Postgres/pgvector → Slack/Gmail
  (replace the ASCII placeholder currently in the README).
- A **"what this demonstrates"** section mapping features → skills: AI agents, LLMs, n8n,
  API integration, document automation, RAG, reporting automation, notifications,
  human-in-the-loop, self-hosting/security.

## CASE-STUDY.md
Frame as automating a **holding company's internal ops**: the problem, the before/after workflow,
the tools integrated, and **measurable outcomes** (triage time, manual touches removed). Concrete
and honest that it is a reference implementation — no inflated numbers.

## SECURITY.md
- Secrets handling (`.env` gitignored, `env_file:` in compose, never in JSON/compose literals).
- DB roles/permissions (least-privilege app role vs. n8n schema; localhost-only port binding).
- **Scaling n8n for production**: queue mode with Redis (main + worker + webhook processes),
  externalized Postgres, encryption key management, and how to add it to compose.

## Screenshots
- `docs/screenshots/` placeholder folder (keep `.gitkeep`).
- `SCREENSHOTS.md` listing exactly which screenshots / Loom clips to capture
  (n8n canvas per workflow, a triage run, a cited RAG answer, the daily report in Slack, etc.).

## Style
Write naturally — vary sentence length, avoid generic AI filler and template conclusions, and
keep claims grounded. (See the humanize-prose skill if a draft reads as slop.)
