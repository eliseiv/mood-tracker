"""Transcription response schema."""

from __future__ import annotations

from pydantic import BaseModel


class TranscriptionResponse(BaseModel):
    """POST /transcriptions."""

    text: str
    detected_language: str | None
