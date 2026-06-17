"""Runtime configuration, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service settings. Values come from the process environment (compose env_file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql://aiops:local-dev-password@postgres:5432/aiops"

    # LLM / embeddings
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # RAG
    rag_low_confidence_threshold: float = 0.35


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()
