"""
Application configuration.

Settings are loaded from environment variables (and optionally a .env file).
All values are validated and typed via pydantic-settings.

Usage:
    from app.config import settings
    print(settings.database_url)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_env: Literal["development", "staging", "production"] = "development"
    secret_key: str = Field(default="dev-secret-change-me", min_length=16)
    debug: bool = False
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    api_v1_prefix: str = "/api/v1"

    # ------------------------------------------------------------------
    # Database (PostgreSQL via asyncpg)
    # ------------------------------------------------------------------
    database_url: str = (
        "postgresql+asyncpg://cairnbooks_app:change-me@localhost:5432/cairnbooks"
    )

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # ------------------------------------------------------------------
    # Celery
    # ------------------------------------------------------------------
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # ------------------------------------------------------------------
    # JWT Auth
    # ------------------------------------------------------------------
    jwt_secret_key: str = Field(default="dev-jwt-secret-change-me", min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ------------------------------------------------------------------
    # Object Storage (S3-compatible)
    # ------------------------------------------------------------------
    storage_endpoint_url: str = "http://localhost:9000"
    storage_access_key_id: str = "minioadmin"
    storage_secret_access_key: str = "minioadmin"
    storage_bucket_name: str = "cairnbooks"
    storage_region: str = "us-east-1"

    # ------------------------------------------------------------------
    # Email (SMTP)
    # ------------------------------------------------------------------
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "noreply@example.com"

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _parse_allowed_hosts(cls, v: object) -> list[str]:
        """Accept a comma-separated string or a list."""
        if isinstance(v, str):
            return [h.strip() for h in v.split(",") if h.strip()]
        return v  # type: ignore[return-value]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Module-level convenience alias
settings: Settings = get_settings()
