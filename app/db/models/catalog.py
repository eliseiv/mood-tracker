"""Catalog models: mood scale levels, emotions, activities."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class MoodScaleLevel(Base):
    """A point on the 1..5 mood scale."""

    __tablename__ = "mood_scale_levels"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    value: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    order: Mapped[int] = mapped_column("order", Integer, nullable=False)


class Emotion(Base):
    """An emotion belonging to a single mood scale level."""

    __tablename__ = "emotions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    scale_level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("mood_scale_levels.id", ondelete="CASCADE"), nullable=False
    )
    order: Mapped[int] = mapped_column("order", Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Activity(Base):
    """A predefined (global) or custom (device-scoped) activity."""

    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # NULL device_id == global predefined activity; otherwise custom.
    device_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("devices.id", ondelete="CASCADE"), nullable=True
    )
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
