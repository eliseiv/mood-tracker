"""PointsLedger (append-only) for gamification."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.db.models.enums import PointsReason


class PointsLedger(Base):
    """Append-only ledger of point deltas; balance is denormalized on Device."""

    __tablename__ = "points_ledger"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[PointsReason] = mapped_column(
        SAEnum(PointsReason, native_enum=False, length=32, validate_strings=True),
        nullable=False,
    )
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("mood_entries.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
