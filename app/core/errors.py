"""Unified error model and exception handlers.

All error responses share the shape::

    {"error": {"code": "...", "message": "...", "details": {...}}}

See docs/04-api-contract.md §3.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base application error mapped to the unified error envelope."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details
        self.headers = headers


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class DeviceIdRequiredError(AppError):
    status_code = 400
    code = "device_id_required"


class DeviceIdInvalidError(AppError):
    status_code = 400
    code = "device_id_invalid"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class EntryNotFoundError(NotFoundError):
    code = "entry_not_found"


class ActivityNotFoundError(NotFoundError):
    code = "activity_not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class EntryInvalidTransitionError(ConflictError):
    code = "entry_invalid_transition"


class EntryAlreadyFinishedError(ConflictError):
    code = "entry_already_finished"


class ActivityDuplicateError(ConflictError):
    code = "activity_duplicate"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class UnsupportedMediaTypeError(AppError):
    status_code = 415
    code = "unsupported_media_type"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, retry_after: int, message: str = "Rate limit exceeded.") -> None:
        super().__init__(
            message,
            details={"retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


class LLMUpstreamError(AppError):
    status_code = 502
    code = "llm_upstream_error"


class LLMUnavailableError(AppError):
    status_code = 503
    code = "llm_unavailable"


def _envelope(code: str, message: str, details: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that render every error in the unified envelope."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope(
                "validation_error",
                "Request validation failed.",
                {"errors": _serialize_validation_errors(exc.errors())},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _http_code_for_status(exc.status_code)
        message = exc.detail if isinstance(exc.detail, str) else code
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, message, None),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "Internal server error.", None),
        )


def _serialize_validation_errors(errors: Sequence[Any]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for err in errors:
        serialized.append(
            {
                "loc": [str(part) for part in err.get("loc", [])],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    return serialized


def _http_code_for_status(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        413: "payload_too_large",
        415: "unsupported_media_type",
        422: "validation_error",
        429: "rate_limited",
    }
    return mapping.get(status_code, "error")
