"""Application configuration loaded from environment variables / ``.env``."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from limits import parse as parse_rate_limit
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

    # ---- Logging ----
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    #: auto = JSON in production/staging, readable text elsewhere
    LOG_FORMAT: Literal["auto", "json", "text"] = "auto"

    # ---- TTS (Text-to-Speech) ----
    #: Provider selection: auto tries piper → espeak; "piper"/"local" force one.
    TTS_PROVIDER: Literal["auto", "piper", "local"] = "auto"
    #: Directory containing Piper .onnx + .onnx.json voice model files.
    PIPER_VOICES_DIR: Path = Path("./voices")
    #: Default Piper voice (file stem, e.g. "en_US-lessac-medium").
    PIPER_DEFAULT_VOICE: str = "en_US-lessac-medium"
    #: Disk cache directory for synthesised audio (must NOT be under STORAGE_DIR).
    TTS_CACHE_DIR: Path = Path("./tts_cache")

    # ---- Per-IP limits for /auth/* (slowapi syntax, e.g. "10/minute") ----
    AUTH_RATE_LIMIT_REGISTER: str = "5/minute"
    AUTH_RATE_LIMIT_LOGIN: str = "10/minute"
    AUTH_RATE_LIMIT_REFRESH: str = "30/minute"
    AUTH_RATE_LIMIT_LOGOUT: str = "30/minute"
    AUTH_RATE_LIMIT_ME: str = "60/minute"

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator(
        "RATE_LIMIT_DEFAULT",
        "AUTH_RATE_LIMIT_REGISTER",
        "AUTH_RATE_LIMIT_LOGIN",
        "AUTH_RATE_LIMIT_REFRESH",
        "AUTH_RATE_LIMIT_LOGOUT",
        "AUTH_RATE_LIMIT_ME",
    )
    @classmethod
    def _validate_rate_limit(cls, value: str) -> str:
        """Fail at startup (not on the first request) when a limit string is malformed."""
        try:
            parse_rate_limit(value)
        except ValueError as exc:
            raise ValueError(f"Invalid rate limit {value!r}; use e.g. '10/minute'") from exc
        return value

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

    @property
    def json_logs(self) -> bool:
        """JSON log lines in production/staging (or when forced)."""
        if self.LOG_FORMAT == "auto":
            return self.ENVIRONMENT in ("production", "staging")
        return self.LOG_FORMAT == "json"


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance (use as a FastAPI dependency)."""
    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()