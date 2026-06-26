"""LLM behaviour (mocked): LLM#1 create, LLM#2 analysis, retries, failures."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIConnectionError, APIError, APITimeoutError
from sqlalchemy import func, select

from app.db.models import MoodEntry
from app.db.session import get_sessionmaker
from tests.helpers import (
    API,
    VALID_ANALYSIS,
    create_awaiting,
    entry_body,
    finish,
    over_limit_analysis,
)

pytestmark = pytest.mark.asyncio

_REQ = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


async def _entry_count(device_id: str) -> int:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return await session.scalar(
            select(func.count())
            .select_from(MoodEntry)
            .where(MoodEntry.device_id == device_id)
        )


# --- LLM#1 (POST /entries) failures: nothing is persisted ------------------
async def test_create_llm_api_error_returns_502_no_entry(client: Any, llm: Any) -> None:
    llm.set_followup(APIError("boom", request=_REQ, body=None))
    r = await client.post(f"{API}/entries", json=entry_body())
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "llm_upstream_error"
    assert await _entry_count(client.device_id) == 0
    history = await client.get(f"{API}/entries?status=finished")
    assert history.json()["items"] == []


async def test_create_llm_timeout_returns_503_no_entry(client: Any, llm: Any) -> None:
    llm.set_followup(APITimeoutError(request=_REQ))
    r = await client.post(f"{API}/entries", json=entry_body())
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "llm_unavailable"
    assert await _entry_count(client.device_id) == 0


async def test_create_llm_connection_error_returns_503_no_entry(client: Any, llm: Any) -> None:
    llm.set_followup(APIConnectionError(message="conn", request=_REQ))
    r = await client.post(f"{API}/entries", json=entry_body())
    assert r.status_code == 503
    assert await _entry_count(client.device_id) == 0


# --- LLM#2 (POST /finish) structured outputs -------------------------------
async def test_analysis_parsed_from_structured_outputs(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await finish(client, llm, entry_id, analysis=VALID_ANALYSIS)
    assert r.status_code == 200
    analysis = r.json()["analysis"]
    assert analysis["title"] == "Work Overwhelm"
    assert len(analysis["advice"]) == 2


async def test_analysis_length_violation_soft_trims_and_finishes(client: Any, llm: Any) -> None:
    """REWORK-1: over-limit after retry -> soft-trim, finish 200, points awarded."""
    entry_id = await create_awaiting(client, llm)
    r = await finish(client, llm, entry_id, analysis=over_limit_analysis())
    assert r.status_code == 200
    analysis = r.json()["analysis"]
    assert len(analysis["title"].split()) <= 3
    assert len(analysis["overview"].split()) <= 40
    assert r.json()["reward"]["points_awarded"] == 20
    assert r.json()["streak"]["current_streak"] == 1
    analysis_calls = [c for c in llm.chat_calls if "response_format" in c]
    assert len(analysis_calls) == 2  # llm_max_retries=1 -> 2 attempts before trim


async def test_analysis_retry_succeeds_on_second_attempt(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await finish(client, llm, entry_id, analysis=[over_limit_analysis(), VALID_ANALYSIS])
    assert r.status_code == 200
    assert r.json()["analysis"]["title"] == "Work Overwhelm"
    analysis_calls = [c for c in llm.chat_calls if "response_format" in c]
    assert len(analysis_calls) == 2


# --- LLM#2 failures: status stays awaiting_answer --------------------------
async def _assert_unchanged(client: Any, entry_id: str) -> None:
    state = await client.get(f"{API}/entries/{entry_id}")
    assert state.json()["status"] == "awaiting_answer"
    assert state.json()["analysis"] is None


async def test_analysis_api_error_returns_502_status_unchanged(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await finish(client, llm, entry_id, analysis=APIError("boom", request=_REQ, body=None))
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "llm_upstream_error"
    await _assert_unchanged(client, entry_id)


async def test_analysis_invalid_json_returns_502_status_unchanged(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await finish(client, llm, entry_id, analysis="this is not json")
    assert r.status_code == 502
    await _assert_unchanged(client, entry_id)


async def test_analysis_empty_choices_returns_502(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await finish(client, llm, entry_id, analysis=SimpleNamespace(choices=[]))
    assert r.status_code == 502
    await _assert_unchanged(client, entry_id)


async def test_analysis_timeout_returns_503_status_unchanged(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await finish(client, llm, entry_id, analysis=APITimeoutError(request=_REQ))
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "llm_unavailable"
    await _assert_unchanged(client, entry_id)


async def test_analysis_connection_error_returns_503(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await finish(client, llm, entry_id, analysis=APIConnectionError(message="c", request=_REQ))
    assert r.status_code == 503
    await _assert_unchanged(client, entry_id)
