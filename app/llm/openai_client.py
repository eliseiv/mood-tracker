"""Async OpenAI client factory.

TLS verification is on by default (httpx). Timeout is enforced; the SDK's own
retries are disabled so retry policy is controlled by callers (ADR-005).
"""

from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import get_settings


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client configured from settings."""
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=0,
    )
