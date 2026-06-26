"""Activity catalog endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_device_id, rate_limit
from app.schemas.catalog import ActivitiesResponse, ActivityOut, CreateActivityRequest
from app.services import catalog as catalog_service

router = APIRouter(tags=["catalog"])


@router.get(
    "/activities",
    response_model=ActivitiesResponse,
    dependencies=[Depends(rate_limit("default"))],
)
async def get_activities(
    device_id: uuid.UUID = Depends(get_device_id),
    session: AsyncSession = Depends(get_db),
) -> ActivitiesResponse:
    """Return predefined plus this device's custom activities."""
    activities = await catalog_service.list_activities(session, device_id)
    return ActivitiesResponse(
        activities=[
            ActivityOut(id=a.id, code=a.code, label=a.label, is_custom=a.is_custom)
            for a in activities
        ]
    )


@router.post(
    "/activities",
    response_model=ActivityOut,
    status_code=201,
    dependencies=[Depends(rate_limit("default"))],
)
async def create_activity(
    body: CreateActivityRequest,
    device_id: uuid.UUID = Depends(get_device_id),
    session: AsyncSession = Depends(get_db),
) -> ActivityOut:
    """Create a custom activity (deduplicated by lower(label) within device)."""
    activity = await catalog_service.create_custom_activity(session, device_id, body.label)
    await session.commit()
    return ActivityOut(
        id=activity.id, code=activity.code, label=activity.label, is_custom=activity.is_custom
    )
