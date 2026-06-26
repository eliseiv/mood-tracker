"""Profile (identity) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_device, get_db
from app.core.config import get_settings
from app.db.models import Device
from app.schemas.me import MeResponse, PointsResponse, StreakResponse

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeResponse)
async def get_me(device: Device = Depends(get_current_device)) -> MeResponse:
    """Return the device profile (created on first access)."""
    return MeResponse(
        device_id=device.id,
        points_balance=device.points_balance,
        current_streak=device.current_streak,
        longest_streak=device.longest_streak,
        last_entry_date=device.last_entry_date,
        language=device.locale,
        timezone=device.timezone,
        created_at=device.created_at,
    )


@router.get("/streak", response_model=StreakResponse)
async def get_streak(device: Device = Depends(get_current_device)) -> StreakResponse:
    """Return streak counters."""
    return StreakResponse(
        current_streak=device.current_streak,
        longest_streak=device.longest_streak,
        last_entry_date=device.last_entry_date,
    )


@router.get("/points", response_model=PointsResponse)
async def get_points(device: Device = Depends(get_current_device)) -> PointsResponse:
    """Return points balance and per-entry reward."""
    return PointsResponse(
        points_balance=device.points_balance,
        points_per_entry=get_settings().points_per_entry,
    )


@router.delete("", status_code=204, response_class=Response)
async def delete_me(
    device: Device = Depends(get_current_device),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Delete the device and all related data (cascade). Irreversible (Q-DATA-1)."""
    await session.delete(device)
    await session.commit()
    return Response(status_code=204)
