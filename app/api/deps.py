"""FastAPI dependencies: device scope, DB session, rate limiting."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import RateLimitedError
from app.core.rate_limit import RateLimiter, limits_for
from app.db.models import Device
from app.db.session import get_db

__all__ = ["get_current_device", "get_db", "get_device_id", "rate_limit"]


def get_device_id(request: Request) -> str:
    """Return the opaque device id placed on request state by the middleware."""
    device_id: str = request.state.device_id
    return device_id


async def get_current_device(request: Request, session: AsyncSession = Depends(get_db)) -> Device:
    """Load the current Device (created by middleware) within the request session."""
    device_id = get_device_id(request)
    device = await session.get(Device, device_id)
    if device is None:
        device = Device(id=device_id)
        session.add(device)
        await session.flush()
    return device


# Categories whose limits also apply per client IP (defense-in-depth against
# device-id rotation on expensive LLM/STT routes — docs/05-security.md).
_IP_LIMITED_CATEGORIES = frozenset({"llm", "transcription"})


def _client_ip(request: Request) -> str | None:
    """Resolve the client IP, honouring X-Forwarded-For only behind a trusted proxy."""
    settings = get_settings()
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    return request.client.host if request.client else None


def rate_limit(category: str) -> Callable[[Request], Awaitable[None]]:
    """Build a dependency enforcing the rate limit for a route category.

    Keyed by device-id; for expensive LLM/STT categories it is additionally keyed
    by client IP (secondary signal). Exceeding either key yields 429 + Retry-After,
    so rotating the client-controlled device-id does not bypass the limit
    (docs/05-security.md §Rate limiting, threat model).
    """

    async def dependency(request: Request) -> None:
        limiter: RateLimiter = request.app.state.rate_limiter
        settings = get_settings()
        max_requests, window = limits_for(category, settings)
        device_id = getattr(request.state, "device_id", None)

        keys = [f"{category}:device:{device_id}"]
        if category in _IP_LIMITED_CATEGORIES:
            client_ip = _client_ip(request)
            if client_ip is not None:
                keys.append(f"{category}:ip:{client_ip}")

        for key in keys:
            allowed, retry_after = await limiter.hit(key, max_requests, window)
            if not allowed:
                raise RateLimitedError(retry_after)

    return dependency
