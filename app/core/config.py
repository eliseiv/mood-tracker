"""Application settings loaded from environment (pydantic-settings).

Single source of configuration. Secrets (OPENAI_API_KEY, DATABASE_URL) come
only from env / secret manager — never hardcoded (see docs/05-security.md).
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Runtime
    environment: str = "local"
    log_level: str = "INFO"
    # Deployment environment discriminator for the fail-closed app-key guard (ADR-009).
    app_env: Literal["local", "prod"] = "local"

    # Database
    database_url: str = "sqlite+aiosqlite:///./mood_tracker.db"

    # App-level static API key (ADR-009). Secret from env only, never hardcoded/logged.
    # When empty, the X-API-Key barrier is disabled (local/dev); prod sets a value.
    api_key: str = ""

    # OpenAI / LLM. Model ids are configurable (Q-LLM-1) — never hardcoded.
    # Prod default gpt-4o (Structured Outputs strict); pin a dated id via env if needed.
    openai_api_key: str = ""
    openai_text_model: str = "gpt-4o"
    openai_transcribe_model: str = "whisper-1"
    openai_temperature: float = 0.7
    openai_timeout_seconds: float = 30.0
    llm_max_retries: int = 1

    # Rate limiting
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    redis_url: str | None = None
    rate_limit_default_max: int = 120
    rate_limit_default_window: int = 60
    rate_limit_llm_max: int = 10
    rate_limit_llm_window: int = 60
    rate_limit_transcription_max: int = 20
    rate_limit_transcription_window: int = 60
    # Trust X-Forwarded-For for the client IP (enable only behind a trusted proxy/LB).
    trust_proxy_headers: bool = False

    # Upload / text limits
    max_audio_bytes: int = 10_485_760
    max_text_chars: int = 4000

    # Gamification
    points_per_entry: int = 20

    # CORS. NoDecode: take the raw env/dotenv string (no JSON pre-parse) so an
    # empty value and a comma-separated list both work, not only a JSON array.
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_prod_api_key(self) -> Settings:
        """Fail-closed prod guard (ADR-009): refuse to start in prod without a key.

        Raised at Settings initialization (before serving traffic). The key value
        itself is never included in the message.
        """
        if self.app_env == "prod" and not self.api_key:
            raise ValueError(
                "API_KEY must be set when APP_ENV=prod (app-level auth fail-closed guard)."
            )
        return self

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept empty, a comma-separated string, or a JSON array."""
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the cached singleton settings instance."""
    return Settings()
