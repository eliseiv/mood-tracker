"""LLM generation service: follow-up (LLM#1) and structured analysis (LLM#2)."""

from __future__ import annotations

import json
from typing import Any, cast

from openai import APIConnectionError, APIError, APITimeoutError
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.completion_create_params import ResponseFormat

from app.core.config import get_settings
from app.core.errors import LLMUnavailableError, LLMUpstreamError
from app.core.logging import get_logger
from app.llm.analysis_schema import ANALYSIS_RESPONSE_FORMAT, AnalysisPayload
from app.llm.openai_client import get_openai_client
from app.llm.prompts.registry import (
    CURRENT_PROMPT_VERSION,
    build_analysis_prompt,
    build_followup_prompt,
)

logger = get_logger(__name__)

MAX_TITLE_WORDS = 3
MAX_OVERVIEW_WORDS = 40


def _language_system_prompt(language: str) -> str:
    return f"You are an empathetic mental well-being assistant. Respond only in {language}."


def _build_messages(language: str, prompt: str) -> list[ChatCompletionMessageParam]:
    return [
        ChatCompletionSystemMessageParam(role="system", content=_language_system_prompt(language)),
        ChatCompletionUserMessageParam(role="user", content=prompt),
    ]


def _word_count(text: str) -> int:
    return len(text.split())


def _lengths_ok(payload: AnalysisPayload) -> bool:
    return (
        _word_count(payload.title) <= MAX_TITLE_WORDS
        and _word_count(payload.overview) <= MAX_OVERVIEW_WORDS
    )


def _truncate_payload(payload: AnalysisPayload) -> AnalysisPayload:
    """Soft-trim title/overview to the word limits (ADR-005 Variant A)."""
    title = " ".join(payload.title.split()[:MAX_TITLE_WORDS])
    overview = " ".join(payload.overview.split()[:MAX_OVERVIEW_WORDS])
    return payload.model_copy(update={"title": title, "overview": overview})


async def generate_followup_question(
    emotions: str, description_text: str, language: str
) -> tuple[str, str]:
    """Generate the empathic follow-up question (LLM#1).

    Returns ``(question, prompt_version)``. Raises 503/502 on provider failure.
    """
    settings = get_settings()
    client = get_openai_client()
    prompt = build_followup_prompt(emotions, description_text)
    try:
        response = await client.chat.completions.create(
            model=settings.openai_text_model,
            temperature=settings.openai_temperature,
            messages=_build_messages(language, prompt),
        )
    except (APITimeoutError, APIConnectionError) as exc:
        logger.warning("followup_llm_unavailable", error_type=type(exc).__name__)
        raise LLMUnavailableError("LLM service unavailable.") from exc
    except APIError as exc:
        logger.warning("followup_llm_upstream_error", error_type=type(exc).__name__)
        raise LLMUpstreamError("LLM provider error.") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content or not content.strip():
        raise LLMUpstreamError("LLM returned an empty follow-up question.")
    return content.strip(), CURRENT_PROMPT_VERSION


async def generate_analysis(
    emotions: str, text: str, language: str
) -> tuple[AnalysisPayload, str, str, dict[str, Any]]:
    """Generate the structured final analysis (LLM#2).

    Validates length limits with up to ``LLM_MAX_RETRIES`` retries; if still
    violated, soft-trims title/overview to the limits and finishes successfully
    (ADR-005 Variant A). 502 is reserved for real provider failures (APIError,
    empty/invalid JSON); 503 for timeout/connection. Returns
    ``(payload, model, prompt_version, raw_response)``.
    """
    settings = get_settings()
    client = get_openai_client()
    prompt = build_analysis_prompt(emotions, text)
    attempts = settings.llm_max_retries + 1
    last_payload: AnalysisPayload | None = None
    last_raw: dict[str, Any] | None = None

    for attempt in range(attempts):
        try:
            response = await client.chat.completions.create(
                model=settings.openai_text_model,
                temperature=settings.openai_temperature,
                messages=_build_messages(language, prompt),
                response_format=cast(ResponseFormat, ANALYSIS_RESPONSE_FORMAT),
            )
        except (APITimeoutError, APIConnectionError) as exc:
            logger.warning("analysis_llm_unavailable", error_type=type(exc).__name__)
            raise LLMUnavailableError("LLM service unavailable.") from exc
        except APIError as exc:
            logger.warning("analysis_llm_upstream_error", error_type=type(exc).__name__)
            raise LLMUpstreamError("LLM provider error.") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            logger.warning("analysis_empty_response", attempt=attempt)
            continue
        try:
            raw = json.loads(content)
            payload = AnalysisPayload.model_validate(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("analysis_parse_error", attempt=attempt, error_type=type(exc).__name__)
            continue
        last_payload, last_raw = payload, raw
        if _lengths_ok(payload):
            return payload, settings.openai_text_model, CURRENT_PROMPT_VERSION, raw
        logger.warning("analysis_length_violation", attempt=attempt)

    if last_payload is not None and last_raw is not None:
        # Cosmetic length overflow after retry -> soft-trim and finish (200).
        logger.warning(
            "analysis_length_truncated",
            title_words=_word_count(last_payload.title),
            overview_words=_word_count(last_payload.overview),
        )
        truncated = _truncate_payload(last_payload)
        return truncated, settings.openai_text_model, CURRENT_PROMPT_VERSION, last_raw
    # No usable payload at all (empty / invalid JSON across all attempts).
    raise LLMUpstreamError("Analysis could not be generated.")
