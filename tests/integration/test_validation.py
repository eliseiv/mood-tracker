"""Validation rules for the 2-POST lifecycle (all checks before any LLM call)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.helpers import API, create_awaiting, entry_body, finish

pytestmark = pytest.mark.asyncio


# --- POST /entries validation ----------------------------------------------
async def test_mood_required(client: Any) -> None:
    r = await client.post(f"{API}/entries", json={"emotions": [], "description": "hello"})
    assert r.status_code == 422


async def test_mood_out_of_range_returns_422(client: Any) -> None:
    r = await client.post(
        f"{API}/entries", json={"mood": 9, "emotions": [], "description": "hello"}
    )
    assert r.status_code == 422


async def test_emotions_required(client: Any) -> None:
    r = await client.post(f"{API}/entries", json={"mood": 2, "description": "hello"})
    assert r.status_code == 422


async def test_empty_emotions_list_is_valid(client: Any, llm: Any) -> None:
    llm.set_followup("ok?")
    r = await client.post(f"{API}/entries", json=entry_body(mood=2, emotions=[]))
    assert r.status_code == 201


async def test_emotion_not_in_mood_level_returns_422(client: Any) -> None:
    # "anxious" belongs to level 1; mood 5 -> mismatch.
    r = await client.post(f"{API}/entries", json=entry_body(mood=5, emotions=["anxious"]))
    assert r.status_code == 422
    assert "anxious" in r.json()["error"]["details"]["mismatched_emotions"]


async def test_unknown_emotion_code_returns_422(client: Any) -> None:
    r = await client.post(f"{API}/entries", json=entry_body(mood=1, emotions=["bogus"]))
    assert r.status_code == 422
    assert "bogus" in r.json()["error"]["details"]["unknown_emotions"]


async def test_unknown_activity_id_returns_422(client: Any) -> None:
    missing = "11111111-1111-4111-8111-111111111111"
    r = await client.post(f"{API}/entries", json=entry_body(activities=[missing]))
    assert r.status_code == 422
    assert missing in r.json()["error"]["details"]["unknown_activities"]


async def test_invalid_activity_id_format_returns_422(client: Any) -> None:
    r = await client.post(f"{API}/entries", json=entry_body(activities=["not-a-uuid"]))
    assert r.status_code == 422


async def test_description_required_nonempty(client: Any) -> None:
    r = await client.post(f"{API}/entries", json={"mood": 2, "emotions": [], "description": ""})
    assert r.status_code == 422


async def test_description_whitespace_only_returns_422(client: Any) -> None:
    r = await client.post(f"{API}/entries", json=entry_body(description="   "))
    assert r.status_code == 422


async def test_description_over_max_chars_returns_422(client: Any) -> None:
    r = await client.post(f"{API}/entries", json=entry_body(description="a" * 4001))
    assert r.status_code == 422
    assert r.json()["error"]["details"]["max_chars"] == 4000


async def test_validation_failure_does_not_call_llm(client: Any, llm: Any) -> None:
    # mood mismatch -> 422 must happen before LLM#1.
    r = await client.post(f"{API}/entries", json=entry_body(mood=5, emotions=["anxious"]))
    assert r.status_code == 422
    assert llm.chat_calls == []


# --- POST /finish validation -----------------------------------------------
async def test_finish_answer_required_nonempty(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await client.post(f"{API}/entries/{entry_id}/finish", json={"answer": ""})
    assert r.status_code == 422


async def test_finish_answer_over_max_returns_422(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await finish(client, llm, entry_id, answer="a" * 4001)
    assert r.status_code == 422
