"""Orchestration tying together chunking, embeddings, retrieval, and the LLM."""

from __future__ import annotations

from typing import Any

from app import db, embeddings, extraction, llm, rag
from app.config import get_settings
from app.models import (
    AnswerRequest,
    AnswerResponse,
    Citation,
    ExtractResponse,
    IngestRequest,
    IngestResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)

# Fields whose absence means the extraction needs a human to review it.
_EXPECTED_INVOICE_FIELDS = ("vendor", "invoice_number", "invoice_date", "currency", "total")


def ingest_documents(req: IngestRequest) -> IngestResponse:
    """Chunk each document, embed the chunks, and upsert them into pgvector."""
    chunk_texts: list[str] = []
    pending: list[tuple[Any, int, str]] = []  # (document, chunk_index, chunk_text)
    for doc in req.documents:
        for idx, chunk in enumerate(rag.chunk_text(doc.text, req.chunk_size, req.chunk_overlap)):
            chunk_texts.append(chunk)
            pending.append((doc, idx, chunk))

    if not chunk_texts:
        return IngestResponse(ingested_documents=0, ingested_chunks=0)

    # Idempotent re-ingest: drop prior chunks for these sources first.
    db.delete_sources(sorted({doc.source for doc in req.documents}))

    vectors = embeddings.embed_texts(chunk_texts)
    rows: list[dict[str, Any]] = [
        {
            "source": doc.source,
            "title": doc.title,
            "chunk_index": idx,
            "content": chunk,
            "embedding": vec,
            "metadata": {**doc.metadata, "chunk_index": idx},
        }
        for (doc, idx, chunk), vec in zip(pending, vectors)
    ]
    db.upsert_chunks(rows)
    return IngestResponse(
        ingested_documents=len({doc.source for doc in req.documents}),
        ingested_chunks=len(rows),
    )


def _retrieve(query: str, top_k: int) -> tuple[list[SearchHit], float]:
    """Hybrid retrieval. Returns (top_k fused hits, best evidence confidence in 0..1)."""
    query_vec = embeddings.embed_texts([query])[0]
    pool = max(top_k * 4, 20)

    vector_rows = db.vector_search(query_vec, pool)
    fulltext_rows = db.fulltext_search(query, pool)

    by_id: dict[int, tuple[Any, ...]] = {}
    sim_by_id: dict[int, float] = {}
    for row in vector_rows:
        by_id[row[0]] = row
        sim_by_id[row[0]] = float(row[5])
    for row in fulltext_rows:
        by_id.setdefault(row[0], row)

    fused = rag.reciprocal_rank_fusion(
        [[r[0] for r in vector_rows], [r[0] for r in fulltext_rows]]
    )
    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]

    hits: list[SearchHit] = []
    confidence = 0.0
    for chunk_id, fused_score in ranked:
        row = by_id[chunk_id]
        content = row[4]
        vector_sim = sim_by_id.get(chunk_id, 0.0)
        # Confidence = best of (semantic similarity, lexical term coverage of the
        # evidence). Robust whether using real embeddings or the offline fallback.
        evidence_conf = max(vector_sim, rag.term_coverage(query, content))
        confidence = max(confidence, evidence_conf)
        hits.append(
            SearchHit(
                chunk_id=chunk_id,
                source=row[1],
                title=row[2],
                chunk_index=row[3],
                score=round(fused_score, 6),
                vector_similarity=round(vector_sim, 6),
                snippet=rag.snippet(content, query),
                content=content,
            )
        )
    return hits, round(confidence, 6)


def search(req: SearchRequest) -> SearchResponse:
    hits, _ = _retrieve(req.query, req.top_k)
    return SearchResponse(query=req.query, hits=hits)


def answer(req: AnswerRequest) -> AnswerResponse:
    hits, confidence = _retrieve(req.query, req.top_k)
    threshold = get_settings().rag_low_confidence_threshold
    low_confidence = confidence < threshold

    contexts = [{"source": h.source, "title": h.title, "content": h.content} for h in hits]
    text = llm.generate_answer(req.query, contexts)
    citations = [
        Citation(source=h.source, chunk_id=h.chunk_id, title=h.title, score=h.score)
        for h in hits
    ]
    return AnswerResponse(
        answer=text,
        citations=citations,
        low_confidence=low_confidence,
        confidence=confidence,
    )


def extract_invoice_document(text: str, source_file: str | None = None) -> ExtractResponse:
    """Extract structured invoice fields, flag gaps, and persist valid invoices."""
    ext = extraction.extract_invoice(text)

    missing = [f for f in _EXPECTED_INVOICE_FIELDS if getattr(ext, f) in (None, "")]
    if not ext.line_items:
        missing.append("line_items")
    low_confidence = bool(missing)

    # Persist only documents that are recognisably an invoice (have an id + total),
    # so a non-invoice never writes a garbage row.
    persisted = False
    invoice_id: int | None = None
    if ext.invoice_number and ext.total is not None:
        invoice_id = db.insert_invoice(
            vendor=ext.vendor,
            invoice_number=ext.invoice_number,
            invoice_date=ext.invoice_date,
            due_date=ext.due_date,
            currency=ext.currency,
            total=ext.total,
            line_items=[li.model_dump() for li in ext.line_items],
            source_file=source_file,
            low_confidence=low_confidence,
            raw_extraction=ext.model_dump(),
        )
        persisted = True

    return ExtractResponse(
        extraction=ext,
        low_confidence=low_confidence,
        missing_fields=missing,
        persisted=persisted,
        invoice_id=invoice_id,
    )
