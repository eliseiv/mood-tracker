"""Catalog service: moods, activities, validation of catalog references."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ActivityDuplicateError, ValidationError
from app.db.models import Activity, Emotion, MoodScaleLevel
from app.llm.language import parse_accept_language


def resolve_catalog_language(query_language: str | None, accept_language: str | None) -> str:
    """Resolve catalog label language (ADR-010): ?language= -> Accept-Language -> en.

    Recognizes the primary subtag: ``ru``/``ru-RU`` -> ``ru``; anything else -> ``en``.
    """
    raw = query_language or parse_accept_language(accept_language) or "en"
    primary = raw.split("-")[0].strip().lower()
    return "ru" if primary == "ru" else "en"


async def list_levels_with_emotions(
    session: AsyncSession,
) -> list[tuple[MoodScaleLevel, list[Emotion]]]:
    """Return mood levels (ordered) each with their active emotions (ordered)."""
    levels = (await session.scalars(select(MoodScaleLevel).order_by(MoodScaleLevel.order))).all()
    emotions = (
        await session.scalars(
            select(Emotion).where(Emotion.is_active.is_(True)).order_by(Emotion.order)
        )
    ).all()
    by_level: dict[uuid.UUID, list[Emotion]] = {}
    for emotion in emotions:
        by_level.setdefault(emotion.scale_level_id, []).append(emotion)
    return [(level, by_level.get(level.id, [])) for level in levels]


async def list_activities(session: AsyncSession, device_id: str) -> list[Activity]:
    """Return predefined (global) plus this device's custom activities."""
    stmt = (
        select(Activity)
        .where(or_(Activity.device_id.is_(None), Activity.device_id == device_id))
        .order_by(Activity.is_custom, Activity.label)
    )
    return list((await session.scalars(stmt)).all())


async def create_custom_activity(session: AsyncSession, device_id: str, label: str) -> Activity:
    """Create a custom activity, deduplicated by lower(label) within the device."""
    normalized = label.strip()
    if not normalized:
        raise ValidationError("Activity label must not be empty.")
    existing = await session.scalar(
        select(Activity).where(
            Activity.device_id == device_id,
            func.lower(Activity.label) == normalized.lower(),
        )
    )
    if existing is not None:
        raise ActivityDuplicateError("Activity already exists for this device.")
    activity = Activity(
        label=normalized,
        code=None,
        device_id=device_id,
        is_custom=True,
    )
    session.add(activity)
    await session.flush()
    return activity


async def resolve_level(session: AsyncSession, mood_value: int) -> MoodScaleLevel:
    """Resolve a mood scale level by its 1..5 value."""
    level = await session.scalar(select(MoodScaleLevel).where(MoodScaleLevel.value == mood_value))
    if level is None:
        raise ValidationError("Unknown mood value.", details={"mood": mood_value})
    return level


async def resolve_emotions(
    session: AsyncSession, codes: list[str], level: MoodScaleLevel
) -> list[Emotion]:
    """Resolve emotion codes and verify each belongs to the given mood level.

    Only active emotions are selectable; retired (``is_active=false``) legacy codes
    resolve as unknown -> 422 (ADR-010 migration deactivates the old catalog).
    """
    if not codes:
        return []
    unique_codes = list(dict.fromkeys(codes))
    emotions = (
        await session.scalars(
            select(Emotion).where(Emotion.code.in_(unique_codes), Emotion.is_active.is_(True))
        )
    ).all()
    found = {emotion.code: emotion for emotion in emotions}
    unknown = [code for code in unique_codes if code not in found]
    if unknown:
        raise ValidationError("Unknown emotion code(s).", details={"unknown_emotions": unknown})
    mismatched = [code for code in unique_codes if found[code].scale_level_id != level.id]
    if mismatched:
        raise ValidationError(
            "Emotion(s) do not match the selected mood level.",
            details={"mismatched_emotions": mismatched, "mood": level.value},
        )
    return [found[code] for code in unique_codes]


async def resolve_activities(
    session: AsyncSession, device_id: str, activity_ids: list[str]
) -> list[Activity]:
    """Resolve activity ids scoped to global + this device; unknown -> 422."""
    if not activity_ids:
        return []
    parsed: list[uuid.UUID] = []
    for raw in dict.fromkeys(activity_ids):
        try:
            parsed.append(uuid.UUID(raw))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValidationError("Invalid activity id.", details={"activity_id": raw}) from exc
    stmt = select(Activity).where(
        Activity.id.in_(parsed),
        or_(Activity.device_id.is_(None), Activity.device_id == device_id),
    )
    activities = (await session.scalars(stmt)).all()
    found = {activity.id: activity for activity in activities}
    unknown = [str(aid) for aid in parsed if aid not in found]
    if unknown:
        raise ValidationError("Unknown activity id(s).", details={"unknown_activities": unknown})
    return [found[aid] for aid in parsed]
