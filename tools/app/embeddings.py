"""Embedding generation with a configurable provider and an offline fallback.

Provider selection (``EMBEDDING_PROVIDER``):
  * ``openai`` — real call to the embeddings API (used when a real key is set).
  * ``local``  — deterministic hashing embedding; no network, no key.

If ``openai`` is configured but the key is still a placeholder, we fall back to
``local`` so the suite stays demoable out of the box. Local embeddings are good
enough for lexical/keyword overlap (and tests); swap in a real key for semantic
quality.
"""

from __future__ import annotations

import hashlib
import math
import re

import httpx

from app.config import get_settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _is_placeholder(key: str | None) -> bool:
    return not key or "replace" in key.lower()


def _local_embed_one(text: str, dim: int) -> list[float]:
    """Deterministic signed-hashing bag-of-words embedding, L2-normalized."""
    vec = [0.0] * dim
    for tok in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha1(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _local_embed(texts: list[str], dim: int) -> list[list[float]]:
    return [_local_embed_one(t, dim) for t in texts]


def _openai_embed(texts: list[str], model: str, key: str, dim: int) -> list[list[float]]:
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "input": texts},
        timeout=60.0,
    )
    resp.raise_for_status()
    data = sorted(resp.json()["data"], key=lambda d: d["index"])
    vectors: list[list[float]] = [d["embedding"] for d in data]
    if vectors and len(vectors[0]) != dim:
        raise ValueError(
            f"Embedding model returned dim {len(vectors[0])}, expected {dim}. "
            "Update EMBEDDING_DIM and the documents.embedding column to match."
        )
    return vectors


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input text."""
    settings = get_settings()
    dim = settings.embedding_dim
    provider = settings.embedding_provider.lower()
    if provider == "openai" and not _is_placeholder(settings.openai_api_key):
        assert settings.openai_api_key is not None  # narrowed by the guard above
        return _openai_embed(texts, settings.embedding_model, settings.openai_api_key, dim)
    return _local_embed(texts, dim)
