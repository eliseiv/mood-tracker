"""Entry lifecycle (2-POST), analysis and history endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_device_id, rate_limit
from app.api.serializers import analysis_to_out, entry_to_full_response
from app.core.errors import EntryNotFoundError, ValidationError
from app.db.models.enums import EntryStatus
from app.schemas.entries import (
    AnalysisOut,
    CreateEntryRequest,
    CreateEntryResponse,
    EntryResponse,
    FinishRequest,
    FinishResponse,
    HistoryItem,
    HistoryResponse,
    RewardOut,
    StreakOut,
)
from app.services import entry as entry_service

router = APIRouter(tags=["entries"])


@router.post(
    "/entries",
    response_model=CreateEntryResponse,
    status_code=201,
    dependencies=[Depends(rate_limit("llm"))],
)
async def create_entry(
    body: CreateEntryRequest,
    request: Request,
    device_id: str = Depends(get_device_id),
) -> CreateEntryResponse:
    """Create an entry and generate the follow-up question (LLM#1).

    The service manages its own short transactions and does not hold a DB
    connection during the LLM call. On LLM failure (502/503) nothing is created.
    """
    result = await entry_service.create_entry(
        device_id,
        mood=body.mood,
        emotions=body.emotions,
        activities=body.activities,
        description=body.description,
        source=body.source,
        language=body.language,
        accept_language=request.headers.get("Accept-Language"),
        timezone=body.timezone,
    )
    return CreateEntryResponse(
        entry_id=result.entry_id,
        status=result.status,
        question=result.question,
        prompt_version=result.prompt_version,
    )


@router.get(
    "/entries",
    response_model=HistoryResponse,
    dependencies=[Depends(rate_limit("default"))],
)
async def list_entries(
    status: str = "finished",
    limit: int = 20,
    cursor: str | None = None,
    device_id: str = Depends(get_device_id),
    session: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    """List finished entries with cursor pagination (finished_at DESC)."""
    if status != "finished":
        raise ValidationError("Only status=finished is supported.", details={"status": status})
    if limit < 1 or limit > 50:
        raise ValidationError("limit must be between 1 and 50.", details={"limit": limit})
    rows, next_cursor = await entry_service.list_finished_entries(
        session, device_id, limit=limit, cursor=cursor
    )
    items: list[HistoryItem] = []
    for entry in rows:
        if entry.finished_at is None:
            continue
        title = entry.analysis.title if entry.analysis is not None else ""
        items.append(
            HistoryItem(
                id=entry.id,
                mood=entry.mood_level.value,
                emotions=[emotion.code for emotion in entry.emotions],
                title=title,
                finished_at=entry.finished_at,
            )
        )
    return HistoryResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/entries/{entry_id}",
    response_model=EntryResponse,
    dependencies=[Depends(rate_limit("default"))],
)
async def get_entry(
    entry_id: uuid.UUID,
    device_id: str = Depends(get_device_id),
    session: AsyncSession = Depends(get_db),
) -> EntryResponse:
    """Return the full state of an entry."""
    entry = await entry_service.get_entry(session, device_id, entry_id)
    return entry_to_full_response(entry)


@router.post(
    "/entries/{entry_id}/finish",
    response_model=FinishResponse,
    dependencies=[Depends(rate_limit("llm"))],
)
async def post_finish(
    entry_id: uuid.UUID,
    body: FinishRequest,
    device_id: str = Depends(get_device_id),
) -> FinishResponse:
    """Answer the follow-up, generate analysis (LLM#2), award points, update streak.

    The service manages its own short transactions and does not hold a DB
    connection during the LLM call.
    """
    result = await entry_service.finish_entry(
        device_id, entry_id, answer=body.answer, source=body.source
    )
    return FinishResponse(
        analysis=analysis_to_out(result.analysis),
        reward=RewardOut(
            points_awarded=result.points_awarded, points_balance=result.points_balance
        ),
        streak=StreakOut(
            current_streak=result.current_streak, longest_streak=result.longest_streak
        ),
    )


@router.get(
    "/entries/{entry_id}/analysis",
    response_model=AnalysisOut,
    dependencies=[Depends(rate_limit("default"))],
)
async def get_analysis(
    entry_id: uuid.UUID,
    device_id: str = Depends(get_device_id),
    session: AsyncSession = Depends(get_db),
) -> AnalysisOut:
    """Return the analysis of a finished entry."""
    entry = await entry_service.get_entry(session, device_id, entry_id)
    if entry.status != EntryStatus.FINISHED or entry.analysis is None:
        raise EntryNotFoundError("Analysis not found.")
    return analysis_to_out(entry.analysis)
