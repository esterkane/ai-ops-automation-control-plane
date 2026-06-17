"""LLM answer generation with a configurable provider and an offline fallback.

Providers (``LLM_PROVIDER``): ``openai`` (chat completions), ``anthropic``
(messages API), or ``local`` (extractive — stitches the top evidence together).
When a real key is absent the local path is used so the demo answers offline.
"""

from __future__ import annotations

import httpx

from app.config import get_settings

SYSTEM_PROMPT = (
    "You are a precise internal-support assistant. Answer the question using ONLY the "
    "provided context. If the context does not contain the answer, say you don't have "
    "enough information. Cite the bracketed source numbers you used, e.g. [1]."
)


def _is_placeholder(key: str | None) -> bool:
    return not key or "replace" in key.lower()


def _format_context(contexts: list[dict[str, str]]) -> str:
    blocks = []
    for i, c in enumerate(contexts, start=1):
        blocks.append(f"[{i}] (source: {c['source']} — {c['title']})\n{c['content']}")
    return "\n\n".join(blocks)


def _build_user_prompt(query: str, contexts: list[dict[str, str]]) -> str:
    return (
        f"Context:\n{_format_context(contexts)}\n\n"
        f"Question: {query}\n\n"
        "Answer using only the context above, and cite the bracketed sources you used."
    )


def _openai_answer(query: str, contexts: list[dict[str, str]], model: str, key: str) -> str:
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(query, contexts)},
            ],
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    content: str = resp.json()["choices"][0]["message"]["content"]
    return content.strip()


def _anthropic_answer(query: str, contexts: list[dict[str, str]], model: str, key: str) -> str:
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
        json={
            "model": model,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": _build_user_prompt(query, contexts)}],
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    content: str = resp.json()["content"][0]["text"]
    return content.strip()


def _local_answer(query: str, contexts: list[dict[str, str]]) -> str:
    if not contexts:
        return "I don't have enough information in the knowledge base to answer that."
    top = " ".join(contexts[0]["content"].split())
    if len(top) > 600:
        top = top[:600].rsplit(" ", 1)[0] + "…"
    cites = ", ".join(f"[{i}]" for i in range(1, len(contexts) + 1))
    return (
        f"Based on the internal knowledge base, here is what the most relevant "
        f"sources say: {top} (sources: {cites})"
    )


def generate_answer(query: str, contexts: list[dict[str, str]]) -> str:
    """Generate a grounded answer from retrieved context chunks."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "openai" and not _is_placeholder(settings.openai_api_key):
        assert settings.openai_api_key is not None
        return _openai_answer(query, contexts, settings.llm_model, settings.openai_api_key)
    if provider == "anthropic" and not _is_placeholder(settings.anthropic_api_key):
        assert settings.anthropic_api_key is not None
        return _anthropic_answer(query, contexts, settings.llm_model, settings.anthropic_api_key)
    return _local_answer(query, contexts)
