"""Whisper transcription (ADR-004). Audio is processed in memory, never stored."""

from __future__ import annotations

from openai import APIConnectionError, APIError, APITimeoutError

from app.core.config import get_settings
from app.core.errors import LLMUnavailableError, LLMUpstreamError
from app.core.logging import get_logger
from app.llm.language import normalize_whisper_language
from app.llm.openai_client import get_openai_client

logger = get_logger(__name__)


async def transcribe_audio(
    audio: bytes, filename: str, content_type: str
) -> tuple[str, str | None]:
    """Transcribe audio bytes via Whisper.

    Returns ``(text, detected_language_iso639_1)``. Raises ``LLMUnavailableError``
    (503) on timeout/connection issues and ``LLMUpstreamError`` (502) on provider
    errors or an unusable response.
    """
    settings = get_settings()
    client = get_openai_client()
    try:
        response = await client.audio.transcriptions.create(
            model=settings.openai_transcribe_model,
            file=(filename, audio, content_type),
            response_format="verbose_json",
        )
    except (APITimeoutError, APIConnectionError) as exc:
        logger.warning("whisper_unavailable", error_type=type(exc).__name__)
        raise LLMUnavailableError("Transcription service unavailable.") from exc
    except APIError as exc:
        logger.warning("whisper_upstream_error", error_type=type(exc).__name__)
        raise LLMUpstreamError("Transcription provider error.") from exc

    text = getattr(response, "text", None)
    if text is None:
        raise LLMUpstreamError("Transcription returned no text.")
    raw_language = getattr(response, "language", None)
    detected = normalize_whisper_language(raw_language)
    return text, detected
