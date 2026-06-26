"""Catalog request/response schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class EmotionOut(BaseModel):
    """An emotion within a mood level (GET /moods)."""

    code: str
    label: str
    order: int


class LevelOut(BaseModel):
    """A mood scale level with its emotions (GET /moods)."""

    value: int
    code: str
    label: str
    order: int
    emotions: list[EmotionOut]


class MoodsResponse(BaseModel):
    """GET /moods."""

    levels: list[LevelOut]


class ActivityOut(BaseModel):
    """An activity (GET/POST /activities)."""

    id: uuid.UUID
    code: str | None
    label: str
    is_custom: bool


class ActivitiesResponse(BaseModel):
    """GET /activities."""

    activities: list[ActivityOut]


class CreateActivityRequest(BaseModel):
    """POST /activities body."""

    label: str = Field(min_length=1, max_length=100)
