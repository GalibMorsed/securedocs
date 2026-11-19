from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and backend/.env."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "SecureDocs"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+psycopg://securedocs:securedocs_password@localhost:5432/securedocs"
    )
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None

    embedding_provider: Literal["openrouter"] = "openrouter"
    embedding_model: Literal["qwen/qwen3-embedding-8b"] = "qwen/qwen3-embedding-8b"
    embedding_dimensions: Literal[4096] = 4096
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    chat_model: str = "qwen/qwen3-30b-a3b-instruct-2507"
    chat_monthly_token_limit: int = 10_000_000
    chat_max_output_tokens: int = 900
    chat_history_messages: int = 8
    chat_context_chunks: int = 8
    rag_min_similarity: float = 0.20
    embedding_timeout_seconds: float = 20.0
    chat_timeout_seconds: float = 60.0
    embedding_max_retries: int = 3
    embedding_retry_backoff_seconds: int = 2
    embedding_batch_size: int = 64
    embedding_max_document_tokens: int = 100_000
    embedding_max_query_tokens: int = 2_048
    embedding_monthly_token_limit: int = 25_000_000
    ocr_languages: str = "eng"
    ocr_dpi: int = 200
    ocr_max_pages: int = 250

    storage_backend: Literal["local", "s3"] = "local"
    local_storage_path: Path = Path("private_uploads")
    upload_max_bytes: int = 10 * 1024 * 1024
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_prefix: str = "securedocs"
    s3_server_side_encryption: Literal["AES256", "aws:kms"] = "AES256"

    cors_origins: list[str] = ["http://localhost:5173"]
    jwt_secret_key: str = Field(
        default="development-only-change-this-secret-before-deploying", min_length=32
    )
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = 60
    jwt_issuer: str = "securedocs-api"

    @model_validator(mode="after")
    def validate_auth_settings(self) -> "Settings":
        if self.access_token_expire_minutes < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be at least 1")
        if (
            self.environment != "development"
            and self.jwt_secret_key
            == "development-only-change-this-secret-before-deploying"
        ):
            raise ValueError("Set a unique JWT_SECRET_KEY outside development")
        if self.environment != "development" and len(self.jwt_secret_key) < 48:
            raise ValueError("JWT_SECRET_KEY must be at least 48 characters outside development")
        if self.upload_max_bytes < 1:
            raise ValueError("UPLOAD_MAX_BYTES must be at least 1")
        if self.embedding_timeout_seconds <= 0:
            raise ValueError("EMBEDDING_TIMEOUT_SECONDS must be greater than 0")
        if self.chat_timeout_seconds <= 0:
            raise ValueError("CHAT_TIMEOUT_SECONDS must be greater than 0")
        if self.embedding_max_retries < 0:
            raise ValueError("EMBEDDING_MAX_RETRIES cannot be negative")
        if self.embedding_retry_backoff_seconds < 1:
            raise ValueError("EMBEDDING_RETRY_BACKOFF_SECONDS must be at least 1")
        if self.embedding_batch_size < 1 or self.embedding_batch_size > 2_048:
            raise ValueError("EMBEDDING_BATCH_SIZE must be between 1 and 2048")
        if self.embedding_max_document_tokens < 1 or self.embedding_max_query_tokens < 1:
            raise ValueError("Embedding token limits must be positive")
        if self.embedding_monthly_token_limit < 1:
            raise ValueError("EMBEDDING_MONTHLY_TOKEN_LIMIT must be at least 1")
        if self.chat_monthly_token_limit < 1 or self.chat_max_output_tokens < 1:
            raise ValueError("Chat token limits must be positive")
        if self.chat_history_messages < 0 or self.chat_context_chunks < 1:
            raise ValueError("Chat history/context limits are invalid")
        if not 0 <= self.rag_min_similarity <= 1:
            raise ValueError("RAG_MIN_SIMILARITY must be between 0 and 1")
        if self.ocr_dpi < 72 or self.ocr_max_pages < 1 or not self.ocr_languages.strip():
            raise ValueError("OCR language, DPI, and page limits must be valid")
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
