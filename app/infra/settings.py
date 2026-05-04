"""Project settings loaded from environment variables.

Uses ``pydantic-settings`` so each setting is type-checked and documented in
one place. ``.env`` files are loaded automatically when present.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Project-wide runtime settings.

    Attributes:
        openai_api_key: Required for synthesis agents and the dense embedder.
        qdrant_url: Vector store endpoint.
        postgres_dsn: Postgres connection string used by LangGraph checkpoints.
        langfuse_host: Langfuse server URL.
        langfuse_public_key: Langfuse public API key.
        langfuse_secret_key: Langfuse secret API key.
        llm_model: OpenAI model identifier for synthesis.
        llm_temperature: Synthesis temperature; default 0.0 for determinism.
        embedding_model: OpenAI embedding model identifier.
        nli_model: Hugging Face NLI model identifier.
        nli_threshold: Compliance Guard entailment probability threshold.
        llm_cache_dir: On-disk content-hash cache directory for LLM calls.
        log_level: Standard logging level name.
        synthetic_data_seed: Seed for deterministic synthetic data generation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    postgres_dsn: str = Field(
        default="postgresql://m25d:m25d_dev_password@localhost:5432/m25d",
        alias="POSTGRES_DSN",
    )
    langfuse_host: str = Field(default="http://localhost:3000", alias="LANGFUSE_HOST")
    langfuse_public_key: str = Field(default="pk-lf-local", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="sk-lf-local", alias="LANGFUSE_SECRET_KEY")
    llm_model: str = Field(default="gpt-4o", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")
    embedding_model: str = Field(default="text-embedding-3-large", alias="EMBEDDING_MODEL")
    nli_model: str = Field(default="microsoft/deberta-v3-large-mnli", alias="NLI_MODEL")
    nli_threshold: float = Field(default=0.75, alias="NLI_THRESHOLD")
    llm_cache_dir: Path = Field(default=Path("eval/.cache"), alias="LLM_CACHE_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    synthetic_data_seed: int = Field(default=42, alias="SYNTHETIC_DATA_SEED")


def get_settings() -> Settings:
    """Return a fresh ``Settings`` instance.

    The instance is intentionally not cached so tests can monkeypatch
    environment variables between test cases.
    """
    return Settings()
