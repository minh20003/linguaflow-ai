"""Application configuration, loaded once per process from the environment.

Fields are grouped into blocks by concern; add a setting inside the block it
belongs to rather than at the end of the class, so parallel branches editing
different concerns do not collide.

`jwt_secret` is the one field with no usable default — it must come from the
environment. Everything else defaults so the test suite and the evaluation
harness can run without a `.env` file.
"""

import logging
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # LLM
    llm_provider: Literal["groq", "deepseek", "gemini", "openai"] = "groq"
    llm_model: str = ""  # Empty = use the provider default (see services/llm.py)
    # Translation is not a creative task — a low temperature keeps the model on
    # the format rules in TRANSLATE_SYSTEM_PROMPT instead of paraphrasing.
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    llm_timeout_seconds: int = Field(default=10, ge=1, le=120)
    # Caps generation cost. A chat message never needs more; anything longer is
    # the model explaining itself, which validate_output rejects anyway.
    llm_max_tokens: int = Field(default=1024, ge=64, le=8192)

    # API key per provider — only the one matching LLM_PROVIDER needs a value
    groq_api_key: str = ""
    deepseek_api_key: str = ""
    google_api_key: str = ""
    openai_api_key: str = ""

    # Agent — number of recent messages used as translation context (PRD: 3-5)
    agent_context_size: int = Field(default=5, ge=0, le=20)
    # Deadline for one whole translation run, covering detection, the LLM call
    # and the secondary provider. The per-call timeouts below do not bound the
    # total, so this is what stops a background task running forever (ADR-14).
    translation_timeout_seconds: int = Field(default=30, ge=5, le=300)

    # Secondary translation provider tried when the LLM path fails (ADR-07).
    # Disable to go straight back to returning the untranslated message.
    fallback_translator_enabled: bool = True
    fallback_translator_timeout_seconds: int = Field(default=5, ge=1, le=30)

    # Observability — Langfuse (F-03.4). Empty keys disable tracing.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    # Accepts either env name. The Langfuse SDK itself reads LANGFUSE_BASE_URL,
    # so a .env written against the SDK's own docs would otherwise be dropped by
    # `extra="ignore"` and silently fall back to the EU default — which answers
    # 401 to a US key. The region here must match the region the keys came from.
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"),
    )

    # Database. The driver must be async — `create_async_engine` cannot open a
    # bare `sqlite://` URL, so the default carries the aiosqlite driver.
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"
    upload_dir: str = "./data/uploads"
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, ge=1)

    # JWT Authentication
    jwt_secret: str = ""  # Required: set in environment
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=1440, ge=1, le=10080)  # 24h default, max 7 days
    refresh_expire_days: int = Field(default=30, ge=1, le=90)
    password_reset_expire_minutes: int = Field(default=30, ge=5, le=120)

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_set(cls, v: str, info) -> str:
        """Ensure JWT secret is not empty in production."""
        if not v:
            raise ValueError(
                "JWT_SECRET environment variable is required. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v


def configure_logging(settings: Settings | None = None) -> None:
    """Apply LOG_LEVEL to the root logger.

    Without this the root logger stays at its WARNING default and every
    ``logger.info`` in the agent is discarded — including the record of when a
    translation fell back, which is the main operational signal the agent emits.

    LOG_LEVEL is applied to the ``src`` logger only, not the root. Setting the
    root level would switch on INFO for every installed library — ``httpx`` alone
    emits one request line per LLM call, which would bury the evaluation
    harness's own progress output.

    Safe to call more than once: the handler is replaced rather than stacked, so
    repeated calls cannot duplicate every line.

    Args:
        settings: Configuration to read. Defaults to the process settings.
    """
    settings = settings or get_settings()

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    app_logger = logging.getLogger("src")
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.setLevel(settings.log_level)
    # Handled here, so don't also hand records to whatever the root has attached.
    app_logger.propagate = False

    # Tracing failures happen on the OTel exporter's background thread, in a
    # logger outside the `src` tree. Left alone they reach stderr unformatted via
    # logging.lastResort and would vanish entirely the day a file handler is
    # added. Attached at WARNING so their routine INFO chatter stays out.
    for name in ("opentelemetry", "langfuse"):
        library_logger = logging.getLogger(name)
        library_logger.handlers.clear()
        library_logger.addHandler(handler)
        library_logger.setLevel(logging.WARNING)
        library_logger.propagate = False


@lru_cache
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()

