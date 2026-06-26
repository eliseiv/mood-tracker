"""Rate limiting (fixed-window) keyed by device-id and route category.

Two backends (docs/05-security.md):
- memory  — local/dev, in-process.
- redis   — prod, shared across workers.

Stricter limits apply to expensive LLM/STT routes (transcriptions, followup,
finish). Exceeding a limit yields HTTP 429 with a ``Retry-After`` header.
"""

from __future__ import annotations

import math
import time
from asyncio import Lock
from typing import Protocol

from app.core.config import Settings


class RateLimiter(Protocol):
    """Fixed-window limiter interface."""

    async def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Register one hit.

        Returns ``(allowed, retry_after_seconds)``. ``retry_after`` is 0 when
        allowed.
        """
        ...


class MemoryRateLimiter:
    """In-process fixed-window counter. Suitable for a single worker/dev."""

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[int, float]] = {}
        self._lock = Lock()

    async def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        now = time.monotonic()
        async with self._lock:
            count, window_start = self._buckets.get(key, (0, now))
            if now - window_start >= window:
                count, window_start = 0, now
            count += 1
            self._buckets[key] = (count, window_start)
            if count > limit:
                retry_after = max(1, math.ceil(window - (now - window_start)))
                return False, retry_after
        return True, 0


class RedisRateLimiter:
    """Distributed fixed-window counter backed by Redis INCR/EXPIRE."""

    def __init__(self, redis_url: str) -> None:
        # Imported lazily so the dependency is only required for the redis
        # backend (prod). redis.asyncio ships with the redis package.
        from redis.asyncio import Redis

        self._redis = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)

    async def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        redis_key = f"ratelimit:{key}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            await self._redis.expire(redis_key, window)
        if count > limit:
            ttl = await self._redis.ttl(redis_key)
            retry_after = ttl if ttl and ttl > 0 else window
            return False, int(retry_after)
        return True, 0


def build_rate_limiter(settings: Settings) -> RateLimiter:
    """Construct the configured rate limiter backend."""
    if settings.rate_limit_backend == "redis":
        if not settings.redis_url:
            raise RuntimeError("REDIS_URL is required when RATE_LIMIT_BACKEND=redis")
        return RedisRateLimiter(settings.redis_url)
    return MemoryRateLimiter()


def limits_for(category: str, settings: Settings) -> tuple[int, int]:
    """Return ``(max_requests, window_seconds)`` for a route category."""
    if category == "llm":
        return settings.rate_limit_llm_max, settings.rate_limit_llm_window
    if category == "transcription":
        return settings.rate_limit_transcription_max, settings.rate_limit_transcription_window
    return settings.rate_limit_default_max, settings.rate_limit_default_window
