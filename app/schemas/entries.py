"""Entry lifecycle request/response schemas (2-POST lifecycle, ADR-003)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.enums import EntryStatus, MessageRole, MessageSource

# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class CreateEntryRequest(BaseModel):
    """POST /entries body (create + LLM#1 follow-up)."""

    mood: int = Field(ge=1, le=5)
    emotions: list[str]
    activities: list[str] = Field(default_factory=list)
    description: str = Field(min_length=1)
    source: MessageSource = MessageSource.TEXT
    language: str | None = Field(default=None, max_length=35)
    timezone: str | None = Field(default=None, max_length=64)


class FinishRequest(BaseModel):
    """POST /entries/{id}/finish body (answer + LLM#2 analysis)."""

    answer: str = Field(min_length=1)
    source: MessageSource = MessageSource.TEXT


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class EntryActivityOut(BaseModel):
    """Activity reference inside an entry response."""

    id: uuid.UUID
    label: str


class MessageOut(BaseModel):
    """An entry message."""

    role: MessageRole
    content: str
    source: MessageSource | None
    prompt_version: str | None
    created_at: datetime


class AdviceOut(BaseModel):
    """An advice section."""

    heading: str
    body: str


class AnalysisOut(BaseModel):
    """Analysis embedded in a full entry / GET analysis / finish."""

    title: str
    overview: str
    advice: list[AdviceOut]
    language: str
    created_at: datetime


class CreateEntryResponse(BaseModel):
    """POST /entries response (status=awaiting_answer + follow-up question)."""

    entry_id: uuid.UUID
    status: EntryStatus
    question: str
    prompt_version: str


class EntryResponse(BaseModel):
    """Full entry state (GET /entries/{id})."""

    id: uuid.UUID
    status: EntryStatus
    mood: int
    emotions: list[str]
    activities: list[EntryActivityOut]
    language: str | None
    messages: list[MessageOut]
    analysis: AnalysisOut | None
    created_at: datetime
    finished_at: datetime | None


class RewardOut(BaseModel):
    """Points reward block (finish)."""

    points_awarded: int
    points_balance: int


class StreakOut(BaseModel):
    """Streak block (finish)."""

    current_streak: int
    longest_streak: int


class FinishResponse(BaseModel):
    """POST /entries/{id}/finish response."""

    analysis: AnalysisOut
    reward: RewardOut
    streak: StreakOut


class HistoryItem(BaseModel):
    """One finished entry in history."""

    id: uuid.UUID
    mood: int
    emotions: list[str]
    title: str
    finished_at: datetime


class HistoryResponse(BaseModel):
    """GET /entries history page."""

    items: list[HistoryItem]
    next_cursor: str | None
