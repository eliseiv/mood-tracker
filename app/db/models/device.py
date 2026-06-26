"""Device model — anonymous device == user (ADR-007)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Device(Base):
    """Anonymous device identified by the ``X-Device-Id`` header.

    ``id`` is an opaque client-supplied string (ADR-007); a UUID is a valid
    special case. Stored verbatim (no normalization/mapping).
    """

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # DB column ``locale``; exposed as ``language`` in the API (BCP-47).
    locale: Mapped[str | None] = mapped_column(String(35), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    points_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
