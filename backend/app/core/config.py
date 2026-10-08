"""Application configuration loaded from environment variables / ``.env``."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are read from process environment variables first, then from the
    ``.env`` file in the current working directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---- Core ----
    PROJECT_NAME: str = "EduConnect"
    VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ---- Database ----
    DATABASE_URL: str

    # ---- JWT ----
    JWT_SECRET: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, gt=0)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, gt=0)

    # ---- Storage ----
    STORAGE_DIR: Path = Path("./storage")
    MAX_UPLOAD_SIZE_MB: int = Field(default=25, gt=0)

    # ---- CORS ----
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # ---- Redis / rate limiting ----
    REDIS_URL: str = "redis://localhost:6379/0"
    RATE_LIMIT_DEFAULT: str = "120/minute"
    RATE_LIMIT_STORAGE_URI: str = "memory://"

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator("DATABASE_URL")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        """Ensure the async asyncpg driver is used."""
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must start with 'postgresql+asyncpg://'")
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        """Accept a comma-separated string or a JSON array."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                value = json.loads(value)
            else:
                value = [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list) and "*" in value:
            raise ValueError("Wildcard CORS origin is not allowed when credentials are enabled")
        return value

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Refuse to boot in production with a placeholder JWT secret."""
        if self.ENVIRONMENT == "production" and "change-me" in self.JWT_SECRET.lower():
            raise ValueError("JWT_SECRET must be changed in production")
        return self

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        """Return ``True`` when running in production."""
        return self.ENVIRONMENT == "production"

    @property
    def max_upload_size_bytes(self) -> int:
        """Maximum upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance (use as a FastAPI dependency)."""
    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()