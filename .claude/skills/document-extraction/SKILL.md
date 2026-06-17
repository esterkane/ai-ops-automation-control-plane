---
name: document-extraction
description: Implement the /extract document-processing endpoint in the FastAPI tools service — accept an invoice/form PDF, extract text, use an LLM with a strict JSON schema to pull structured fields (vendor, invoice number, date, line items, total, currency), validate against Pydantic, flag low-confidence/missing fields, and write a row to the invoices table. Includes sample PDFs and tests. Use for invoice parsing, document automation, or structured-extraction work in this repo. (Prompt 3.)
---

# Document extraction (Prompt 3)

Add a document-processing endpoint to `tools/app/`.

## Endpoint: POST `/extract`
- Accept an uploaded invoice/form **PDF** (`multipart/form-data`).
- Extract text — implement `extraction.extract_text_from_pdf` with `pypdf`
  (poppler-utils is already in the Dockerfile for fallback OCR-adjacent tooling).
- Call the LLM (via `LLM_PROVIDER`/`LLM_MODEL`) with a **strict JSON schema** to pull:
  `vendor`, `invoice_number`, `invoice_date`, `due_date`, `currency`, `total`,
  and `line_items[]` (`description`, `quantity`, `unit_price`, `amount`).
- **Validate** the LLM output against a Pydantic `InvoiceExtraction` model.
- **Flag** `low_confidence` when required fields are missing/unparseable or the model
  signals uncertainty; surface which fields are weak.
- On success, **write a row to `app.invoices`** (store `raw_extraction` JSON + `low_confidence`).
  Upsert on `(vendor, invoice_number)` to stay idempotent.

## Rules
- Typed Pydantic request/response models; never return raw dicts.
- Don't invent fields — if the document isn't an invoice, return `low_confidence: true`
  with empty/None fields rather than hallucinating values.
- DB writes go through `app/db.py`; every schema change needs an init/migration update.

## Samples & tests
- Add 2–3 sample PDFs under `tools/tests/fixtures/` (or `samples/`):
  a clean invoice, a messy/low-quality one, and a non-invoice document.
- Tests cover all three: clean → all fields + row written; messy → partial + `low_confidence`;
  non-invoice → `low_confidence`, no garbage row. Patch the LLM call for determinism.

## Verify & report
End with the standard verification block (pytest / ruff / mypy / manual smoke uploading a sample PDF).
