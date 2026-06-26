"""MoodEntry, association tables and EntryMessage."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    Uuid,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.db.models.analysis import AnalysisResult
from app.db.models.catalog import Activity, Emotion, MoodScaleLevel
from app.db.models.enums import EntryStatus, MessageRole, MessageSource

entry_emotions = Table(
    "entry_emotions",
    Base.metadata,
    Column(
        "entry_id",
        Uuid(),
        ForeignKey("mood_entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "emotion_id",
        Uuid(),
        ForeignKey("emotions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

entry_activities = Table(
    "entry_activities",
    Base.metadata,
    Column(
        "entry_id",
        Uuid(),
        ForeignKey("mood_entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "activity_id",
        Uuid(),
        ForeignKey("activities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class MoodEntry(Base):
    """A two-step mood entry resource (ADR-003, 2-POST lifecycle)."""

    __tablename__ = "mood_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[EntryStatus] = mapped_column(
        SAEnum(EntryStatus, native_enum=False, length=32, validate_strings=True),
        default=EntryStatus.AWAITING_ANSWER,
        nullable=False,
    )
    # mood is mandatory in POST /entries -> NOT NULL.
    mood_scale_level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("mood_scale_levels.id"), nullable=False
    )
    language: Mapped[str | None] = mapped_column(String(35), nullable=True)
    points_awarded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    mood_level: Mapped[MoodScaleLevel] = relationship("MoodScaleLevel", lazy="joined")
    emotions: Mapped[list[Emotion]] = relationship(
        "Emotion", secondary=entry_emotions, lazy="selectin"
    )
    activities: Mapped[list[Activity]] = relationship(
        "Activity", secondary=entry_activities, lazy="selectin"
    )
    messages: Mapped[list[EntryMessage]] = relationship(
        "EntryMessage",
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntryMessage.created_at",
        lazy="selectin",
    )
    analysis: Mapped[AnalysisResult | None] = relationship(
        "AnalysisResult",
        back_populates="entry",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )


class EntryMessage(Base):
    """A user or AI message attached to an entry."""

    __tablename__ = "entry_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("mood_entries.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, native_enum=False, length=32, validate_strings=True),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[MessageSource | None] = mapped_column(
        SAEnum(MessageSource, native_enum=False, length=16, validate_strings=True),
        nullable=True,
    )
    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    entry: Mapped[MoodEntry] = relationship("MoodEntry", back_populates="messages")
