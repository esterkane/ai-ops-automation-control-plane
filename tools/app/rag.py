"""Pure retrieval helpers: chunking, reciprocal rank fusion, snippets, coverage.

Kept side-effect free so they're trivially unit-testable.
"""

from __future__ import annotations

import io
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "what", "which", "who", "whom",
    "how", "does", "did", "can", "could", "should", "would", "with", "from",
    "this", "that", "these", "those", "your", "our", "their", "about", "into",
    "have", "has", "had", "will", "you", "they", "them", "its", "his", "her",
}


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into overlapping character windows, trimmed."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    step = max(1, size - overlap)
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunk = text[start : start + size].strip()
        if chunk:
            chunks.append(chunk)
        if start + size >= len(text):
            break
        start += step
    return chunks


def reciprocal_rank_fusion(ranked_lists: list[list[int]], k: int = 60) -> dict[int, float]:
    """Fuse multiple rank-ordered id lists. score(id) = Σ 1 / (k + rank)."""
    scores: dict[int, float] = {}
    for ids in ranked_lists:
        for rank, id_ in enumerate(ids):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k + rank + 1)
    return scores


def meaningful_terms(query: str) -> set[str]:
    """Content-bearing query terms (lowercase, >2 chars, not stopwords)."""
    return {t for t in _TOKEN_RE.findall(query.lower()) if len(t) > 2 and t not in _STOPWORDS}


def term_coverage(query: str, content: str) -> float:
    """Fraction of meaningful query terms present in the evidence content (0..1)."""
    terms = meaningful_terms(query)
    if not terms:
        return 0.0
    present = {t for t in terms if t in content.lower()}
    return len(present) / len(terms)


def snippet(content: str, query: str, width: int = 240) -> str:
    """A short evidence window centred on the first matching query term."""
    low = content.lower()
    pos = -1
    for term in meaningful_terms(query):
        found = low.find(term)
        if found != -1:
            pos = found
            break
    if pos == -1:
        return content[:width].strip()
    start = max(0, pos - 60)
    end = min(len(content), start + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(content) else ""
    return prefix + content[start:end].strip() + suffix


def read_pdf_text(data: bytes) -> str:
    """Extract text from a PDF byte payload (used by /ingest for PDF uploads)."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)
