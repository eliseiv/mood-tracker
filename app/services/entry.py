"""Entry lifecycle service (2-POST, three-phase LLM connection management).

POST /entries  : create + LLM#1 follow-up   -> awaiting_answer  (ADR-003)
POST /finish   : answer + LLM#2 analysis     -> finished

Both endpoints follow the three-phase pattern (ADR-008): a short read-only
transaction to validate/gather, the LLM call with NO DB connection held, then a
short write transaction. finish locks the entry row (FOR UPDATE OF mood_entries)
and the Device row (FOR UPDATE) to serialize points/streak and stay idempotent.
"""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    EntryAlreadyFinishedError,
    EntryInvalidTransitionError,
    EntryNotFoundError,
    ValidationError,
)
from app.db.base import utcnow
from app.db.models import (
    Activity,
    AdviceSection,
    AnalysisResult,
    Device,
    Emotion,
    EntryMessage,
    MoodEntry,
)
from app.db.models.enums import EntryStatus, MessageRole, MessageSource
from app.db.session import get_sessionmaker
from app.llm.language import ensure_language, resolve_entry_language
from app.services import catalog as catalog_service
from app.services.analysis import generate_analysis, generate_followup_question
from app.services.points import award_entry_points
from app.services.streak import local_date, set_device_timezone, update_streak


@dataclass
class CreateEntryResult:
    """Outcome of POST /entries."""

    entry_id: uuid.UUID
    status: EntryStatus
    question: str
    prompt_version: str


@dataclass
class FinishResult:
    """Outcome of POST /entries/{id}/finish."""

    analysis: AnalysisResult
    points_awarded: int
    points_balance: int
    current_streak: int
    longest_streak: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_text(text: str) -> str:
    """Validate non-empty text within the configured character limit."""
    if not text.strip():
        raise ValidationError("Text must not be empty.")
    max_chars = get_settings().max_text_chars
    if len(text) > max_chars:
        raise ValidationError(
            "Text exceeds maximum length.",
            details={"max_chars": max_chars, "length": len(text)},
        )
    return text


def _message_content(entry: MoodEntry, role: MessageRole) -> str:
    for message in entry.messages:
        if message.role == role:
            return message.content
    return ""


def _emotion_labels(emotions: list[Emotion]) -> str:
    return ", ".join(emotion.label for emotion in emotions)


def _ensure_finishable(entry: MoodEntry) -> None:
    if entry.status == EntryStatus.FINISHED:
        raise EntryAlreadyFinishedError("Entry is already finished.")
    if entry.status != EntryStatus.AWAITING_ANSWER:
        raise EntryInvalidTransitionError(
            "Entry cannot be finished in the current status.",
            details={
                "current_status": entry.status.value,
                "required_status": EntryStatus.AWAITING_ANSWER.value,
            },
        )


async def get_entry(session: AsyncSession, device_id: str, entry_id: uuid.UUID) -> MoodEntry:
    """Load an entry scoped to the device; foreign/missing -> 404."""
    entry = await session.scalar(
        select(MoodEntry).where(MoodEntry.id == entry_id, MoodEntry.device_id == device_id)
    )
    if entry is None:
        raise EntryNotFoundError("Entry not found.")
    return entry


async def _get_entry_for_update(
    session: AsyncSession, device_id: str, entry_id: uuid.UUID
) -> MoodEntry:
    """Load an entry scoped to the device, locking its row (FOR UPDATE OF mood_entries).

    ``of=MoodEntry`` avoids locking the outer-joined mood_scale_levels table.
    Real row lock on PostgreSQL; no-op on SQLite (acceptable for local/CI).
    """
    entry = await session.scalar(
        select(MoodEntry)
        .where(MoodEntry.id == entry_id, MoodEntry.device_id == device_id)
        .with_for_update(of=MoodEntry)
    )
    if entry is None:
        raise EntryNotFoundError("Entry not found.")
    return entry


# ---------------------------------------------------------------------------
# POST /entries — create + LLM#1
# ---------------------------------------------------------------------------


async def create_entry(
    device_id: str,
    *,
    mood: int,
    emotions: list[str],
    activities: list[str],
    description: str,
    source: MessageSource,
    language: str | None,
    accept_language: str | None,
    timezone: str | None,
) -> CreateEntryResult:
    """Create an entry and its follow-up question (LLM#1), three-phase (ADR-008).

    The DB connection is not held during the LLM call. The entry is persisted
    only if LLM#1 succeeds; on LLM failure (502/503) nothing is written.
    """
    description = _validate_text(description)
    sessionmaker = get_sessionmaker()

    # Phase 1: validate catalog references and gather prompt data (read-only).
    async with sessionmaker() as session:
        level = await catalog_service.resolve_level(session, mood)
        resolved_emotions = await catalog_service.resolve_emotions(session, emotions, level)
        resolved_activities = await catalog_service.resolve_activities(
            session, device_id, activities
        )
        level_id = level.id
        emotion_ids = [emotion.id for emotion in resolved_emotions]
        activity_ids = [activity.id for activity in resolved_activities]
        emotion_labels = _emotion_labels(resolved_emotions)

    # Language is fixed at creation and reused by both LLM calls (ADR-006).
    effective_language = ensure_language(
        resolve_entry_language(language, accept_language), description
    )

    # Phase 2: LLM#1 with no DB connection held.
    question, prompt_version = await generate_followup_question(
        emotion_labels, description, effective_language
    )

    # Phase 3: persist atomically (only on LLM success).
    async with sessionmaker() as session:
        device = await session.get(Device, device_id)
        if device is None:
            device = Device(id=device_id)
            session.add(device)

        entry = MoodEntry(
            device_id=device_id,
            status=EntryStatus.AWAITING_ANSWER,
            mood_scale_level_id=level_id,
            language=effective_language,
        )
        entry.emotions = await _fetch_ordered_emotions(session, emotion_ids)
        entry.activities = await _fetch_ordered_activities(session, activity_ids)

        now = utcnow()
        entry.messages = [
            EntryMessage(
                role=MessageRole.USER_DESCRIPTION,
                content=description,
                source=source,
                created_at=now,
            ),
            EntryMessage(
                role=MessageRole.AI_FOLLOWUP,
                content=question,
                source=None,
                prompt_version=prompt_version,
                created_at=now + timedelta(milliseconds=1),
            ),
        ]

        if language:
            device.locale = language
        set_device_timezone(device, timezone)

        session.add(entry)
        await session.commit()
        entry_id = entry.id
        status = entry.status

    return CreateEntryResult(
        entry_id=entry_id, status=status, question=question, prompt_version=prompt_version
    )


async def _fetch_ordered_emotions(
    session: AsyncSession, emotion_ids: list[uuid.UUID]
) -> list[Emotion]:
    if not emotion_ids:
        return []
    fetched = (await session.scalars(select(Emotion).where(Emotion.id.in_(emotion_ids)))).all()
    by_id = {emotion.id: emotion for emotion in fetched}
    return [by_id[i] for i in emotion_ids if i in by_id]


async def _fetch_ordered_activities(
    session: AsyncSession, activity_ids: list[uuid.UUID]
) -> list[Activity]:
    if not activity_ids:
        return []
    fetched = (await session.scalars(select(Activity).where(Activity.id.in_(activity_ids)))).all()
    by_id = {activity.id: activity for activity in fetched}
    return [by_id[i] for i in activity_ids if i in by_id]


# ---------------------------------------------------------------------------
# POST /entries/{id}/finish — answer + LLM#2
# ---------------------------------------------------------------------------


async def finish_entry(
    device_id: str, entry_id: uuid.UUID, *, answer: str, source: MessageSource
) -> FinishResult:
    """Answer the follow-up, generate analysis (LLM#2), award points, update streak.

    Three-phase (ADR-008): the DB connection is not held during the LLM call.
    Phase 3 locks the entry row (FOR UPDATE OF mood_entries) and the Device row
    (FOR UPDATE) — re-checks the status guard and serializes points + streak.
    Idempotency/race safety: status guard under lock + unique indexes
    (IntegrityError -> 409 entry_already_finished, no double award).
    """
    answer = _validate_text(answer)
    sessionmaker = get_sessionmaker()

    # Phase 1: load + status guard + gather prompt data (read-only).
    async with sessionmaker() as session:
        entry = await get_entry(session, device_id, entry_id)
        _ensure_finishable(entry)
        emotion_labels = _emotion_labels(entry.emotions)
        description = _message_content(entry, MessageRole.USER_DESCRIPTION)
        entry_language = entry.language

    combined = f"{description}\n{answer}".strip()
    language = ensure_language(entry_language, description, answer)

    # Phase 2: LLM#2 with no DB connection held.
    payload, model, prompt_version, raw = await generate_analysis(
        emotion_labels, combined, language
    )

    points = get_settings().points_per_entry

    # Phase 3: atomic write under row locks (entry + device).
    async with sessionmaker() as session:
        entry = await _get_entry_for_update(session, device_id, entry_id)
        _ensure_finishable(entry)
        device = await session.scalar(
            select(Device).where(Device.id == device_id).with_for_update()
        )
        if device is None:
            raise EntryNotFoundError("Entry not found.")

        entry.messages.append(
            EntryMessage(role=MessageRole.USER_FOLLOWUP_ANSWER, content=answer, source=source)
        )

        analysis = AnalysisResult(
            entry_id=entry.id,
            title=payload.title,
            overview=payload.overview,
            language=language,
            model=model,
            prompt_version=prompt_version,
            raw_response=raw,
        )
        analysis.advice_sections = [
            AdviceSection(position=index, heading=item.heading, body=item.body)
            for index, item in enumerate(payload.advice)
        ]
        session.add(analysis)

        entry.language = language
        entry.status = EntryStatus.FINISHED
        entry.finished_at = utcnow()
        entry.points_awarded = points

        await award_entry_points(session, device, entry.id, points)
        today = local_date(utcnow(), device.timezone)
        update_streak(device, today)

        try:
            await session.commit()
        except IntegrityError as exc:
            # Concurrent finish of the same entry: the losing transaction violates
            # the unique index on analysis_results.entry_id / points_ledger
            # (entry_id, reason). Surface a clean 409 instead of a 500.
            await session.rollback()
            raise EntryAlreadyFinishedError("Entry is already finished.") from exc

        # points_balance was bumped via an atomic SQL UPDATE (not the ORM object),
        # so reload the committed value for the response.
        await session.refresh(device)
        return FinishResult(
            analysis=analysis,
            points_awarded=points,
            points_balance=device.points_balance,
            current_streak=device.current_streak,
            longest_streak=device.longest_streak,
        )


# ---------------------------------------------------------------------------
# History (cursor pagination)
# ---------------------------------------------------------------------------


def _encode_cursor(finished_at: datetime, entry_id: uuid.UUID) -> str:
    payload = json.dumps({"finished_at": finished_at.isoformat(), "id": str(entry_id)})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        data = json.loads(decoded)
        return datetime.fromisoformat(data["finished_at"]), uuid.UUID(data["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValidationError("Invalid cursor.") from exc


async def list_finished_entries(
    session: AsyncSession,
    device_id: str,
    *,
    limit: int,
    cursor: str | None,
) -> tuple[list[MoodEntry], str | None]:
    """Return a page of finished entries (finished_at DESC) and the next cursor."""
    stmt = (
        select(MoodEntry)
        .where(
            MoodEntry.device_id == device_id,
            MoodEntry.status == EntryStatus.FINISHED,
        )
        .order_by(MoodEntry.finished_at.desc(), MoodEntry.id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        cursor_finished_at, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (MoodEntry.finished_at < cursor_finished_at)
            | ((MoodEntry.finished_at == cursor_finished_at) & (MoodEntry.id < cursor_id))
        )

    rows = list((await session.scalars(stmt)).all())
    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        if last.finished_at is not None:
            next_cursor = _encode_cursor(last.finished_at, last.id)
    return rows, next_cursor
