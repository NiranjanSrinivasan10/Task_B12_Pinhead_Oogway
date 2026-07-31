"""
backend.app.config
~~~~~~~~~~~~~~~~~~
Centralised settings loaded from environment variables (via .env file).

Uses pydantic-settings so that:
  - Missing *required* vars fail fast at import time with a clear error.
  - Ollama vars have sensible defaults for local dev.
  - Cloud API keys are only required when the corresponding provider is
    actually selected at runtime, not unconditionally at startup.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


class Settings(BaseSettings):
    """App-wide configuration.

    Required vars:
      SUPABASE_DB_URL — always required (the app cannot start without a DB).

    Conditionally required (validated at request time, not startup):
      OPENAI_API_KEY   — needed when llm_provider == "openai"
      ANTHROPIC_API_KEY — needed when llm_provider == "anthropic"

    Optional with defaults:
      OLLAMA_BASE_URL, OLLAMA_MODEL
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database (always required) ───────────────────────────────
    supabase_db_url: str = Field(
        ...,
        description="Async Postgres connection string, e.g. "
        "postgresql+asyncpg://user:pass@host:5432/dbname",
    )

    # ── Cloud LLM keys (optional at startup, validated per-request) ──
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key; required when llm_provider is 'openai'.",
    )
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key; required when llm_provider is 'anthropic'.",
    )

    # ── Ollama (local LLM) ───────────────────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for the Ollama OpenAI-compatible API.",
    )
    ollama_model: str = Field(
        default="llama3.1:8b",
        description="Default Ollama model to use for local inference.",
    )

    # ── Embedding model (fixed, independent of LLM toggle) ───────
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="HuggingFace model ID for local embeddings (384 dims).",
    )
    embedding_dim: int = Field(
        default=384,
        description="Dimension of the embedding vectors.",
    )

    # ── Helpers ──────────────────────────────────────────────────

    def require_openai_key(self) -> str:
        """Return the OpenAI key or raise a clear error."""
        if not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Add it to backend/.env or switch to a local model."
            )
        return self.openai_api_key

    def require_anthropic_key(self) -> str:
        """Return the Anthropic key or raise a clear error."""
        if not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to backend/.env or switch to a different provider."
            )
        return self.anthropic_api_key

    def require_provider_key(self, provider: str) -> str:
        """Validate that the API key for *provider* is available.

        Called at the point-of-use (message send), not at startup,
        so that the app can still boot and serve the health endpoint
        even if a cloud key is missing.
        """
        match provider:
            case "openai":
                return self.require_openai_key()
            case "anthropic":
                return self.require_anthropic_key()
            case "ollama":
                return ""  # no key needed
            case _:
                raise ValueError(f"Unknown LLM provider: {provider!r}")


# Singleton — import this everywhere.
settings = Settings()  # type: ignore[call-arg]
