"""ORM models and metadata aggregation."""

from __future__ import annotations

from app.db.base import Base
from app.db.models.analysis import AdviceSection, AnalysisResult
from app.db.models.catalog import Activity, Emotion, MoodScaleLevel
from app.db.models.device import Device
from app.db.models.entry import (
    EntryMessage,
    MoodEntry,
    entry_activities,
    entry_emotions,
)
from app.db.models.enums import (
    EntryStatus,
    MessageRole,
    MessageSource,
    PointsReason,
)
from app.db.models.gamification import PointsLedger

__all__ = [
    "Activity",
    "AdviceSection",
    "AnalysisResult",
    "Base",
    "Device",
    "Emotion",
    "EntryMessage",
    "EntryStatus",
    "MessageRole",
    "MessageSource",
    "MoodEntry",
    "MoodScaleLevel",
    "PointsLedger",
    "PointsReason",
    "entry_activities",
    "entry_emotions",
]
