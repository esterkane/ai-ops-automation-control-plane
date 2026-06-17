"""Shared test fixtures.

Forces the offline (`local`) embedding + LLM providers so the suite is fast,
deterministic, and needs no API keys. Integration tests use the real Postgres
service from docker-compose (per project policy: no mocking of OpenSearch/Postgres).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Pin providers before any app module reads settings.
os.environ["EMBEDDING_PROVIDER"] = "local"
os.environ["LLM_PROVIDER"] = "local"

from app import db  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.models import IngestDocument, IngestRequest  # noqa: E402
from app.service import ingest_documents  # noqa: E402

_FIXTURE_KB = [
    IngestDocument(
        source="test_handbook",
        title="Test Handbook",
        text=(
            "The annual leave policy grants 25 days of paid vacation per year. "
            "Employees accrue leave monthly and may carry over five unused days."
        ),
        metadata={"category": "hr"},
    ),
    IngestDocument(
        source="test_faq",
        title="Test FAQ",
        text=(
            "Refunds are available within 14 days of purchase. Contact support "
            "with your invoice number to request a refund to the original card."
        ),
        metadata={"category": "product"},
    ),
]

_FIXTURE_SOURCES = [d.source for d in _FIXTURE_KB]


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture
def knowledge_base() -> Iterator[None]:
    """Load a small controlled KB and tear it down afterwards."""
    db.delete_sources(_FIXTURE_SOURCES)
    ingest_documents(IngestRequest(documents=_FIXTURE_KB))
    try:
        yield
    finally:
        db.delete_sources(_FIXTURE_SOURCES)
