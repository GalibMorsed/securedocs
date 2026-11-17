from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
