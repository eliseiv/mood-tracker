"""Health endpoint (no version prefix, no device-id)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness/readiness probe."""
    return {"status": "ok"}
