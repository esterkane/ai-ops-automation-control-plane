"""Generate the sample PDFs used by the /extract tests and demo.

Run inside the tools container:
    python -m scripts.make_sample_invoices
Writes three files into tools/tests/fixtures/:
  * clean_invoice.pdf    — well-structured, every field present
  * messy_invoice.pdf    — partial fields (no dates/currency/line items)
  * meeting_notes.pdf    — not an invoice at all
"""

from __future__ import annotations

import pathlib

from fpdf import FPDF

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures"

CLEAN = """\
ACME Industrial Supplies Ltd
123 Market Street, Springfield
INVOICE
Invoice Number: INV-2024-0042
Invoice Date: 2024-05-17
Due Date: 2024-06-16
Bill To: Northwind Holdings

Line items:
10 x Steel brackets @ 12.50 = 125.00
4 x Industrial adhesive @ 8.75 = 35.00
20 x Safety gloves @ 3.20 = 64.00

Subtotal: 224.00
Tax (20%): 44.80
Total: USD 268.80
"""

MESSY = """\
QuickFix Plumbing
inv no 99812
items: widgets and gizmos, misc parts, labour
no proper dates here, sorry
amount due 540
thanks!!!
"""

NOT_AN_INVOICE = """\
Team Offsite - Meeting Notes
Quarterly planning session
Attendees: Alice, Bob, Carol
We discussed the product roadmap and agreed to prioritise the search feature.
Action items: Alice to draft the spec, Bob to set up the repository.
No budget decisions were made today.
"""


def _write_pdf(text: str, filename: str) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, text)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    pdf.output(str(FIXTURES / filename))


def main() -> None:
    _write_pdf(CLEAN, "clean_invoice.pdf")
    _write_pdf(MESSY, "messy_invoice.pdf")
    _write_pdf(NOT_AN_INVOICE, "meeting_notes.pdf")
    print(f"[samples] wrote 3 PDFs to {FIXTURES}")


if __name__ == "__main__":
    main()
