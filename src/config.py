from functools import lru_cache
from typing import Literal

from pydantic import Field
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
    llm_provider: Literal["groq", "deepseek", "gemini", "openai"] = "groq"
    llm_model: str = ""  # Rỗng = dùng model mặc định của provider (xem services/llm.py)
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_timeout_seconds: int = Field(default=10, ge=1, le=120)

    # API key theo từng provider — chỉ cần điền key của provider đang dùng
    groq_api_key: str = ""
    deepseek_api_key: str = ""
    google_api_key: str = ""
    openai_api_key: str = ""

    # Deprecated: giữ để code template cũ không vỡ, dùng llm_model thay thế
    model_name: str = "gpt-4o-mini"

    # Agent — số tin nhắn gần nhất dùng làm ngữ cảnh (PRD quy định 3-5)
    agent_context_size: int = Field(default=5, ge=0, le=20)

    # Observability — Langfuse (F-03.4). Để trống thì bỏ qua tracing.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()
