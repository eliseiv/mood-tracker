"""Profile (identity) response schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class MeResponse(BaseModel):
    """Device profile (GET /me)."""

    device_id: uuid.UUID
    points_balance: int
    current_streak: int
    longest_streak: int
    last_entry_date: date | None
    language: str | None
    timezone: str | None
    created_at: datetime


class StreakResponse(BaseModel):
    """GET /me/streak."""

    current_streak: int
    longest_streak: int
    last_entry_date: date | None


class PointsResponse(BaseModel):
    """GET /me/points."""

    points_balance: int
    points_per_entry: int
