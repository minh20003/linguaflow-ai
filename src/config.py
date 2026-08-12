from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Database
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
