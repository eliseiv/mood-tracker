"""Mood catalog endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import Emotion, MoodScaleLevel
from app.schemas.catalog import EmotionOut, LevelOut, MoodsResponse
from app.services import catalog as catalog_service

router = APIRouter(tags=["catalog"])


@router.get("/moods", response_model=MoodsResponse)
async def get_moods(
    request: Request,
    language: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> MoodsResponse:
    """Return mood levels with their active emotions, localized labels (ADR-010).

    Label language: ``?language=`` -> ``Accept-Language`` -> ``en``; ``ru*`` -> RU.
    ``code`` is never localized. Only ``is_active=true`` emotions are returned.
    """
    lang = catalog_service.resolve_catalog_language(
        language, request.headers.get("Accept-Language")
    )

    def label(obj: MoodScaleLevel | Emotion) -> str:
        return obj.label_ru if lang == "ru" else obj.label_en

    levels = await catalog_service.list_levels_with_emotions(session)
    return MoodsResponse(
        levels=[
            LevelOut(
                value=level.value,
                code=level.code,
                label=label(level),
                order=level.order,
                emotions=[
                    EmotionOut(code=emotion.code, label=label(emotion), order=emotion.order)
                    for emotion in emotions
                ],
            )
            for level, emotions in levels
        ]
    )
