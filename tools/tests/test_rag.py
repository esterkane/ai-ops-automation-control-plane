"""Unit + integration tests for the RAG pipeline."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import rag
from app.main import app

client = TestClient(app)


# --- Unit tests: pure retrieval helpers ------------------------------------


def test_chunk_text_overlaps_and_covers() -> None:
    text = "abcdefghij" * 20  # 200 chars
    chunks = rag.chunk_text(text, size=80, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 80 for c in chunks)
    # Reassembled content (accounting for overlap) covers the whole text.
    assert chunks[0][0] == "a"
    assert text.endswith(chunks[-1][-10:])


def test_reciprocal_rank_fusion_rewards_agreement() -> None:
    # id 1 ranks top in both lists; id 3 only appears once.
    fused = rag.reciprocal_rank_fusion([[1, 2, 3], [1, 3]])
    assert fused[1] == max(fused.values())
    assert fused[1] > fused[3]


def test_term_coverage() -> None:
    assert rag.term_coverage("refund policy", "our refund policy is generous") == 1.0
    assert rag.term_coverage("refund policy", "completely unrelated text") == 0.0


# --- Integration tests: real endpoints + Postgres --------------------------


def test_ingest_reports_counts(knowledge_base: None) -> None:
    resp = client.post(
        "/ingest",
        json={
            "documents": [
                {"source": "test_tmp", "title": "Tmp", "text": "A short throwaway document."}
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingested_documents"] == 1
    assert body["ingested_chunks"] >= 1
    # cleanup
    from app import db

    db.delete_sources(["test_tmp"])


def test_search_returns_relevant_chunk_first(knowledge_base: None) -> None:
    resp = client.post("/search", json={"query": "refund within 14 days", "top_k": 3})
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert hits, "expected at least one hit"
    assert hits[0]["source"] == "test_faq"
    assert "refund" in hits[0]["content"].lower()


def test_answer_in_domain_has_citations_and_is_confident(knowledge_base: None) -> None:
    resp = client.post("/answer", json={"query": "How many vacation days do employees get?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"], "every answer must carry citations"
    assert body["low_confidence"] is False
    assert body["confidence"] >= 0.35


def test_answer_off_topic_is_low_confidence(knowledge_base: None) -> None:
    resp = client.post(
        "/answer", json={"query": "What is the boiling point of mercury on Jupiter?"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["low_confidence"] is True
