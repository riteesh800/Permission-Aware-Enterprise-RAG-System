import logging
from functools import lru_cache
from typing import Literal

logger = logging.getLogger(__name__)

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Permission-Aware RAG"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    company_prefix: str = "ACME"

    database_url: str = "postgresql+psycopg2://rag:rag@localhost:5432/permission_rag"
    storage_path: str = "./data/uploads"

    jwt_secret: str = Field(default="change-me-jwt-secret-min-32-chars-long!!")
    session_secret: str = Field(default="change-me-session-secret-min-32-chars!!")
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    llm_provider: Literal["local", "ollama", "llamacpp", "openai-compatible", "extractive"] = "extractive"
    llm_model: str = "llama3.2"
    llm_base_url: str = "http://localhost:11434"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"

    embedding_provider: Literal["local", "hash", "openai-compatible"] = "hash"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    embedding_api_url: str = "https://api.openai.com/v1"
    embedding_api_key: str | None = None

    vector_db: Literal["pgvector", "json"] = "pgvector"
    reranker_provider: Literal["none", "local"] = "none"
    reranker_model: str = "BAAI/bge-reranker-base"

    max_upload_mb: int = 20
    top_k: int = 12
    rerank_top_k: int = 5
    chunk_size: int = 600
    chunk_overlap: int = 80
    max_context_tokens: int = 2500

    login_max_attempts: int = 8
    login_lockout_seconds: int = 300
    rate_limit_login: str = "10/minute"
    rate_limit_chat: str = "30/minute"
    rate_limit_default: str = "120/minute"

    seed_on_startup: bool = False

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "RAG ASSISTANT"


    @field_validator("jwt_secret", "session_secret")
    @classmethod
    def secrets_must_be_long(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("Secrets must be at least 32 characters")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment != "test":
        if "change-me" in settings.jwt_secret or "change-me" in settings.session_secret:
            logger.warning("SECURITY WARNING: Default 'change-me' secrets are being used in a non-test environment. Please update JWT_SECRET and SESSION_SECRET.")
    return settings
