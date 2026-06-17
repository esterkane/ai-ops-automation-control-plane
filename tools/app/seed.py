"""Seed the knowledge base with a fake company handbook + product FAQ.

Run via `make seed` (-> `python -m app.seed` inside the tools container).
Idempotent: re-running replaces the seeded sources.
"""

from __future__ import annotations

from app.models import IngestDocument, IngestRequest
from app.service import ingest_documents

HANDBOOK = """\
Northwind Holdings — Employee Handbook (excerpt)

Working hours and remote work.
Standard working hours are 09:00 to 17:30 local time, Monday to Friday. Employees
may work remotely up to three days per week with manager approval. Core
collaboration hours, when everyone should be reachable, are 11:00 to 15:00.

Paid time off.
Full-time employees accrue 25 days of paid annual leave per year, plus public
holidays. Up to five unused days may be carried into the next year and must be
used by 31 March. Sick leave does not count against annual leave; notify your
manager and HR by 10:00 on the day of absence.

Expenses and reimbursement.
Submit expense claims within 30 days through the finance portal. Receipts are
required for any claim over 25 EUR. Approved expenses are reimbursed in the next
payroll cycle. Travel must be booked through the company travel desk.

Equipment and IT.
Every employee receives a laptop and is responsible for its safekeeping. Report
lost or stolen devices to IT security immediately so the device can be wiped.
Password managers are mandatory; never share credentials over chat or email.
"""

FAQ = """\
SupportBrain Product FAQ

What is SupportBrain?
SupportBrain is a self-hosted knowledge assistant that answers questions using
your own documents. It runs entirely on your infrastructure; no data leaves your
network.

How do refunds work?
Customers on a monthly plan can request a full refund within 14 days of purchase.
Annual plans are refundable on a pro-rata basis for the unused months. To request
a refund, contact support with your invoice number; refunds are processed within
five business days to the original payment method.

What are the supported file types for ingestion?
SupportBrain ingests plain text, Markdown, and PDF documents. Scanned PDFs are
supported when an OCR layer is present. Each document is split into overlapping
chunks before indexing.

How is search performed?
Search is hybrid: it combines vector similarity (semantic match) with full-text
keyword search, then fuses the two rankings using reciprocal rank fusion. This
gives strong results for both conceptual questions and exact-term lookups.

How does SupportBrain decide when to escalate to a human?
Every answer carries a confidence score derived from retrieval strength. When the
best supporting evidence is weak, the answer is flagged low-confidence and routed
to a human reviewer instead of being sent automatically.
"""

SEED_DOCUMENTS = [
    IngestDocument(
        source="handbook.md",
        title="Northwind Holdings Employee Handbook",
        text=HANDBOOK,
        metadata={"category": "hr", "seed": True},
    ),
    IngestDocument(
        source="product_faq.md",
        title="SupportBrain Product FAQ",
        text=FAQ,
        metadata={"category": "product", "seed": True},
    ),
]


def main() -> None:
    """Entry point for `python -m app.seed`."""
    result = ingest_documents(IngestRequest(documents=SEED_DOCUMENTS))
    print(
        f"[seed] ingested {result.ingested_documents} documents "
        f"-> {result.ingested_chunks} chunks into the knowledge base."
    )


if __name__ == "__main__":
    main()
