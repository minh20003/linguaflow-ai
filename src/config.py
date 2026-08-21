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

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that look configured but are not. Everything here has been copied out
# of a template at some point, so none of them may guard a real deployment.
_PLACEHOLDER_JWT_SECRETS = frozenset(
    {"your-secret-key-here", "change-me", "changeme", "secret", "dev-secret"}
)
_MIN_PRODUCTION_JWT_SECRET_LENGTH = 32


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
    # Public frontend routed through this project's Cloudflare Tunnel. Keeping
    # it separate from CORS_ORIGINS lets a local development .env retain its
    # localhost values without breaking the deployed browser client.
    public_frontend_origin: str = "https://agent.dquangminh2003.id.vn"
    # Matched against the Origin header when the exact list above does not.
    # Vercel gives every pull request its own hostname, so a preview build can
    # only reach the API through a pattern — for example
    # `https://linguaflow-[a-z0-9-]+\.vercel\.app`. Empty disables it.
    cors_origin_regex: str = ""

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

    # Google Identity Services authentication. This is an OAuth client ID, not
    # a secret; the browser needs the same value to request an ID token.
    google_oauth_client_id: str = ""

    # Agent — number of recent messages used as translation context (PRD: 3-5)
    agent_context_size: int = Field(default=5, ge=0, le=20)
    # Deadline for one whole translation run, covering detection, the LLM call
    # and the secondary provider. The per-call timeouts below do not bound the
    # total, so this is what stops a background task running forever (ADR-14).
    translation_timeout_seconds: int = Field(default=30, ge=5, le=300)

    # Embeddings (ADR-25). pgvector stores and compares the vectors; something
    # still has to produce them, and the requirement that decides the choice is
    # multilingual reach: unless "staging env" and "môi trường stg" land near
    # each other, grouping corrections by meaning is pointless.
    #
    # `local` runs sentence-transformers in-process — no quota, and no message
    # leaves the container, which is the kill switch ADR-15 asks for. It costs
    # a large dependency, so it is an opt-in extra rather than a requirement.
    embedding_provider: Literal["gemini", "openai", "local"] = "gemini"
    # Empty means the provider's default. The width, unlike this, is *not*
    # configurable: it is EMBEDDING_DIM in src/database/models.py, because two
    # developers with different .env files would otherwise describe two
    # different schemas.
    embedding_model: str = ""

    # Both default off, following `fallback_translator_enabled`. Each adds an
    # embedding call to the request path, and NFR-01 is already the tightest
    # figure in the project — turn them on against measurements, not hopes.
    semantic_glossary_enabled: bool = False
    rag_context_enabled: bool = False
    # Cosine similarity a glossary term must reach to be injected without an
    # exact match. Conservative on purpose: a wrongly matched term is *forced*
    # into the translation, which is worse than missing one.
    glossary_similarity_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    rag_top_k: int = Field(default=3, ge=1, le=10)

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
    # bare `postgresql://` URL, so the default carries the asyncpg driver.
    #
    # PostgreSQL rather than SQLite even for development (ADR-22): the glossary,
    # the correction log and the message memory are searched by cosine distance
    # over pgvector columns, and SQLite has no `vector` type at all. Keeping
    # SQLite for development would mean a second retrieval path that production
    # never runs. `docker compose up -d postgres` provides it.
    database_url: str = "postgresql+asyncpg://linguaflow:linguaflow@localhost:5432/linguaflow"
    # PostgreSQL connections opened per process. Kept small on purpose: one
    # WebSocket holds one session for as long as it stays open, so the pool has
    # to be sized against concurrent sockets rather than requests per second.
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=50)

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"
    upload_dir: str = "./data/uploads"
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "attachments"

    # JWT Authentication
    jwt_secret: str = ""  # Required: set in environment
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=1440, ge=1, le=10080)  # 24h default, max 7 days
    refresh_expire_days: int = Field(default=30, ge=1, le=90)
    password_reset_expire_minutes: int = Field(default=30, ge=5, le=120)

    # Email & OTP Verification (Batch F)
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "LinguaFlow"
    smtp_use_tls: bool = True
    email_provider: Literal["smtp", "console", "memory"] = "memory"

    @field_validator("database_url")
    @classmethod
    def database_url_must_name_an_async_driver(cls, v: str) -> str:
        """Rewrite a plain PostgreSQL URL onto the async driver.

        Managed databases hand out `postgres://…` or `postgresql://…`, which
        SQLAlchemy reads as the synchronous psycopg driver. `create_async_engine`
        then fails with "the asyncio extension requires an async driver" — an
        error that says nothing about the connection string it came from. Since
        asyncpg is the only PostgreSQL driver this project installs, the fix is
        never a different one, so it is applied here rather than asked of
        whoever pastes the URL into the deployment settings.
        """
        for prefix in ("postgresql+", "postgres+"):
            if v.startswith(prefix):
                return v
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return f"postgresql+asyncpg://{v[len(prefix):]}"
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        """The allowed origins as a list, from the comma-separated setting.

        Entries are stripped: a value written the way a human writes a list,
        `http://a, http://b`, would otherwise produce ` http://b`, which matches
        no browser Origin header and fails as a CORS error with nothing in the
        logs to explain it.
        """
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        # The browser-facing local development app is part of the documented
        # contract. Keep these origins available even when a machine-level
        # CORS_ORIGINS variable overrides the repository's .env value.
        for local_origin in ("http://localhost:3000", "http://localhost:3001"):
            if local_origin not in origins:
                origins.append(local_origin)
        if self.public_frontend_origin and self.public_frontend_origin not in origins:
            origins.append(self.public_frontend_origin)
        return origins

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_set(cls, v: str, info) -> str:
        """Reject a missing secret anywhere, and a guessable one in production.

        Anyone holding this value can mint a token for any account, so in
        production the placeholder that ships in `.env.example` — which passes an
        "is it empty" check perfectly well — is treated as no secret at all.
        """
        generate = (
            'Generate one with: python -c "import secrets; '
            'print(secrets.token_urlsafe(48))"'
        )
        if not v:
            raise ValueError(f"JWT_SECRET environment variable is required. {generate}")
        if info.data.get("app_env") == "production":
            if v in _PLACEHOLDER_JWT_SECRETS:
                raise ValueError(
                    f"JWT_SECRET is still the example value. {generate}"
                )
            if len(v) < _MIN_PRODUCTION_JWT_SECRET_LENGTH:
                raise ValueError(
                    "JWT_SECRET must be at least "
                    f"{_MIN_PRODUCTION_JWT_SECRET_LENGTH} characters in production. "
                    f"{generate}"
                )
        return v

    @model_validator(mode="after")
    def validate_production_and_email_config(self) -> "Settings":
        """Enforce production email safety and validate required SMTP fields."""
        if self.app_env == "production":
            if self.email_provider in ("memory", "console"):
                raise ValueError(
                    f"EMAIL_PROVIDER='{self.email_provider}' is not allowed in production. "
                    "Production requires EMAIL_PROVIDER='smtp' with valid SMTP credentials."
                )
            if self.email_provider == "smtp":
                missing = []
                if not self.smtp_host or not self.smtp_host.strip():
                    missing.append("SMTP_HOST")
                if not self.smtp_port:
                    missing.append("SMTP_PORT")
                if not self.smtp_user or not self.smtp_user.strip():
                    missing.append("SMTP_USER")
                if not self.smtp_password or not self.smtp_password.strip():
                    missing.append("SMTP_PASSWORD")
                if not self.smtp_from_email or not self.smtp_from_email.strip():
                    missing.append("SMTP_FROM_EMAIL")
                if missing:
                    raise ValueError(
                        f"Production SMTP configuration is missing required fields: {', '.join(missing)}"
                    )
        return self


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

