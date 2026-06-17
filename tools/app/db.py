"""Thin Postgres/pgvector data-access layer for the RAG pipeline.

Uses one short-lived connection per operation (autocommit). Vectors are passed
as ``'[..]'::vector`` string literals so we don't depend on a numpy adapter.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg

from app.config import get_settings


def _vec_literal(vec: list[float]) -> str:
    """Render an embedding as a pgvector text literal."""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


@contextmanager
def get_conn() -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    """Yield an autocommit connection, closed on exit."""
    settings = get_settings()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        yield conn


def delete_sources(sources: list[str]) -> None:
    """Remove all existing chunks for the given sources (idempotent re-ingest)."""
    if not sources:
        return
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM app.documents WHERE source = ANY(%s)", (sources,))


def upsert_chunks(rows: list[dict[str, Any]]) -> None:
    """Insert (or replace) document chunks.

    Each row needs: source, title, chunk_index, content, embedding, metadata.
    """
    if not rows:
        return
    with get_conn() as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO app.documents
                    (source, title, chunk_index, content, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s::vector, %s::jsonb)
                ON CONFLICT (source, chunk_index) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata
                """,
                (
                    r["source"],
                    r["title"],
                    r["chunk_index"],
                    r["content"],
                    _vec_literal(r["embedding"]),
                    json.dumps(r["metadata"]),
                ),
            )


def insert_invoice(
    *,
    vendor: str | None,
    invoice_number: str | None,
    invoice_date: str | None,
    due_date: str | None,
    currency: str | None,
    total: float | None,
    line_items: list[dict[str, Any]],
    source_file: str | None,
    low_confidence: bool,
    raw_extraction: dict[str, Any],
) -> int:
    """Upsert an extracted invoice. Returns the row id.

    Conflict target is the partial unique index on (vendor, invoice_number)
    where invoice_number is not null, so re-extracting the same invoice updates
    in place rather than duplicating.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app.invoices
                (vendor, invoice_number, invoice_date, due_date, currency, total,
                 line_items, source_file, low_confidence, raw_extraction)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)
            ON CONFLICT (vendor, invoice_number) WHERE invoice_number IS NOT NULL
            DO UPDATE SET
                invoice_date = EXCLUDED.invoice_date,
                due_date = EXCLUDED.due_date,
                currency = EXCLUDED.currency,
                total = EXCLUDED.total,
                line_items = EXCLUDED.line_items,
                source_file = EXCLUDED.source_file,
                low_confidence = EXCLUDED.low_confidence,
                raw_extraction = EXCLUDED.raw_extraction
            RETURNING id
            """,
            (
                vendor,
                invoice_number,
                invoice_date,
                due_date,
                currency,
                total,
                json.dumps(line_items),
                source_file,
                low_confidence,
                json.dumps(raw_extraction),
            ),
        )
        row = cur.fetchone()
        assert row is not None  # RETURNING always yields a row
        return int(row[0])


def delete_invoices_by_source(source_file: str) -> None:
    """Remove invoices loaded from a given source file (test cleanup helper)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM app.invoices WHERE source_file = %s", (source_file,))


def vector_search(query_vec: list[float], limit: int) -> list[tuple[Any, ...]]:
    """Top-N by cosine similarity. Returns (id, source, title, chunk_index, content, sim)."""
    lit = _vec_literal(query_vec)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source, title, chunk_index, content,
                   1 - (embedding <=> %s::vector) AS sim
            FROM app.documents
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (lit, lit, limit),
        )
        return cur.fetchall()


def fulltext_search(query: str, limit: int) -> list[tuple[Any, ...]]:
    """Top-N by Postgres full-text rank. Returns (id, source, title, chunk_index, content, rank)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source, title, chunk_index, content,
                   ts_rank_cd(content_tsv, websearch_to_tsquery('english', %s)) AS rank
            FROM app.documents
            WHERE content_tsv @@ websearch_to_tsquery('english', %s)
            ORDER BY rank DESC
            LIMIT %s
            """,
            (query, query, limit),
        )
        return cur.fetchall()
