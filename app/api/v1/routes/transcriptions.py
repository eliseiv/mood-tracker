"""Stateless speech-to-text endpoint (ADR-004)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.audio import read_capped, validate_audio_mime
from app.api.deps import rate_limit
from app.core.config import get_settings
from app.llm.transcription import transcribe_audio
from app.schemas.transcription import TranscriptionResponse

router = APIRouter(tags=["transcriptions"])


@router.post(
    "/transcriptions",
    response_model=TranscriptionResponse,
    dependencies=[Depends(rate_limit("transcription"))],
)
async def create_transcription(
    audio: UploadFile = File(...),
) -> TranscriptionResponse:
    """Transcribe an uploaded audio file. Audio is processed in memory only."""
    settings = get_settings()
    data = await read_capped(audio, settings.max_audio_bytes)
    validate_audio_mime(audio.content_type, data)
    text, detected_language = await transcribe_audio(
        data,
        audio.filename or "audio",
        audio.content_type or "application/octet-stream",
    )
    return TranscriptionResponse(text=text, detected_language=detected_language)
