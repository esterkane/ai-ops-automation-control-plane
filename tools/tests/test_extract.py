"""Integration tests for the /extract document pipeline.

Uses the committed sample PDFs in tests/fixtures/ (regenerate them with
`python -m scripts.make_sample_invoices`). Runs against the real Postgres.
"""

from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)
FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _extract(name: str) -> dict[str, object]:
    path = FIXTURES / name
    with path.open("rb") as fh:
        resp = client.post("/extract", files={"file": (name, fh, "application/pdf")})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture(autouse=True)
def _clean_invoices() -> None:
    for name in ("clean_invoice.pdf", "messy_invoice.pdf", "meeting_notes.pdf"):
        db.delete_invoices_by_source(name)


def test_clean_invoice_extracts_all_fields_and_persists() -> None:
    body = _extract("clean_invoice.pdf")
    ext = body["extraction"]
    assert ext["vendor"] == "ACME Industrial Supplies Ltd"
    assert ext["invoice_number"] == "INV-2024-0042"
    assert ext["invoice_date"] == "2024-05-17"
    assert ext["due_date"] == "2024-06-16"
    assert ext["currency"] == "USD"
    assert ext["total"] == 268.80
    assert len(ext["line_items"]) == 3
    assert body["low_confidence"] is False
    assert body["persisted"] is True
    assert body["invoice_id"] is not None


def test_messy_invoice_is_partial_and_low_confidence() -> None:
    body = _extract("messy_invoice.pdf")
    ext = body["extraction"]
    assert ext["invoice_number"] == "99812"
    assert ext["total"] == 540.0
    assert body["low_confidence"] is True
    missing = body["missing_fields"]
    assert "currency" in missing
    assert "invoice_date" in missing


def test_non_invoice_is_flagged_and_not_persisted() -> None:
    body = _extract("meeting_notes.pdf")
    assert body["low_confidence"] is True
    assert body["persisted"] is False
    assert body["invoice_id"] is None
