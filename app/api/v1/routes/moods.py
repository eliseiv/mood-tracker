"""Mood catalog endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.catalog import EmotionOut, LevelOut, MoodsResponse
from app.services import catalog as catalog_service

router = APIRouter(tags=["catalog"])


@router.get("/moods", response_model=MoodsResponse)
async def get_moods(
    language: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> MoodsResponse:
    """Return mood levels with their emotions. ``language`` is accepted for
    forward compatibility; localized labels depend on seed data (out of scope)."""
    levels = await catalog_service.list_levels_with_emotions(session)
    return MoodsResponse(
        levels=[
            LevelOut(
                value=level.value,
                code=level.code,
                label=level.label,
                order=level.order,
                emotions=[
                    EmotionOut(code=emotion.code, label=emotion.label, order=emotion.order)
                    for emotion in emotions
                ],
            )
            for level, emotions in levels
        ]
    )
