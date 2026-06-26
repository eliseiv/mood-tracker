"""ASGI middleware: device-id identity (ADR-007) and security headers."""

from __future__ import annotations

import re
import secrets
from collections.abc import Awaitable, Callable

from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import Device
from app.db.session import get_sessionmaker

logger = get_logger(__name__)

_HEALTH_PATH = "/health"
_API_PREFIX = "/api/"

# Opaque device id rules (ADR-007): trimmed, non-empty, <=64 chars,
# charset [A-Za-z0-9._-] (UUID is a valid special case). Case-sensitive.
_MAX_DEVICE_ID_LEN = 64
_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

Handler = Callable[[Request], Awaitable[Response]]


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


async def _upsert_device(device_id: str) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        device = await session.get(Device, device_id)
        if device is None:
            session.add(Device(id=device_id))
            try:
                await session.commit()
            except IntegrityError:
                # Concurrent first request created it; just refresh last_seen.
                await session.rollback()
                device = await session.get(Device, device_id)
                if device is not None:
                    device.last_seen_at = utcnow()
                    await session.commit()
        else:
            device.last_seen_at = utcnow()
            await session.commit()


class DeviceIdMiddleware(BaseHTTPMiddleware):
    """App-level API key auth (ADR-009) then ``X-Device-Id`` identity (ADR-007).

    Order on ``/api/v1/*``: X-API-Key (401) -> X-Device-Id (400) -> upsert Device.
    The API key is checked FIRST, so an invalid key short-circuits with 401 and
    no Device is ever created. ``GET /health`` requires neither header.
    """

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        path = request.url.path
        if path == _HEALTH_PATH or not path.startswith(_API_PREFIX):
            return await call_next(request)

        # 1) App-level API key (ADR-009). Enforced only when API_KEY is configured.
        # The key itself is never logged.
        expected_key = get_settings().api_key
        if expected_key:
            provided_key = request.headers.get("X-API-Key")
            if not provided_key:
                return _error_response(401, "api_key_required", "Application API key is required.")
            if not secrets.compare_digest(provided_key, expected_key):
                return _error_response(401, "api_key_invalid", "Application API key is invalid.")

        # 2) Device identity (ADR-007) — only reached with a valid API key.
        # Opaque string id: trim, non-empty, <=64 chars, charset [A-Za-z0-9._-].
        # Stored/echoed verbatim (no normalization); a UUID is a valid special case.
        device_id = (request.headers.get("X-Device-Id") or "").strip()
        if not device_id:
            return _error_response(400, "device_id_required", "X-Device-Id header is required.")
        if len(device_id) > _MAX_DEVICE_ID_LEN or not _DEVICE_ID_RE.match(device_id):
            return _error_response(400, "device_id_invalid", "X-Device-Id is invalid.")

        await _upsert_device(device_id)
        request.state.device_id = device_id
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers to every response."""

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cache-Control", "no-store")
        return response
