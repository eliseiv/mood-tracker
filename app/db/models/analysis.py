"""AnalysisResult and AdviceSection (LLM#2 output)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, json_variant, utcnow

if TYPE_CHECKING:
    from app.db.models.entry import MoodEntry


class AnalysisResult(Base):
    """Generated analysis for a finished entry (1:1)."""

    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("mood_entries.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(35), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_response: Mapped[dict[str, Any]] = mapped_column(json_variant(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    entry: Mapped[MoodEntry] = relationship("MoodEntry", back_populates="analysis")
    advice_sections: Mapped[list[AdviceSection]] = relationship(
        "AdviceSection",
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="AdviceSection.position",
        lazy="selectin",
    )


class AdviceSection(Base):
    """An ordered advice section within an analysis."""

    __tablename__ = "advice_sections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("analysis_results.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    analysis: Mapped[AnalysisResult] = relationship(
        "AnalysisResult", back_populates="advice_sections"
    )
