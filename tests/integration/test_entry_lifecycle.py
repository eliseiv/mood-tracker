"""2-POST entry lifecycle: create (LLM#1) -> finish (LLM#2)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tests.helpers import API, VALID_ANALYSIS, create_awaiting, entry_body, finish

pytestmark = pytest.mark.asyncio


# --- POST /entries (create + LLM#1) ----------------------------------------
async def test_create_entry_returns_awaiting_answer_with_question(client: Any, llm: Any) -> None:
    llm.set_followup("What part of work felt heaviest today?")
    r = await client.post(f"{API}/entries", json=entry_body())
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"entry_id", "status", "question", "prompt_version"}
    assert body["status"] == "awaiting_answer"
    assert body["question"] == "What part of work felt heaviest today?"
    assert body["prompt_version"] == "v1"


async def test_create_entry_persists_user_and_followup_messages(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm, description="Rough day.", source="voice")
    r = await client.get(f"{API}/entries/{entry_id}")
    body = r.json()
    assert body["status"] == "awaiting_answer"
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user_description", "ai_followup"]
    user_msg = body["messages"][0]
    assert user_msg["content"] == "Rough day."
    assert user_msg["source"] == "voice"
    assert user_msg["prompt_version"] is None
    ai_msg = body["messages"][1]
    assert ai_msg["prompt_version"] == "v1"
    assert ai_msg["source"] is None
    assert body["analysis"] is None
    assert body["finished_at"] is None


async def test_create_entry_passes_language_to_llm(client: Any, llm: Any) -> None:
    await create_awaiting(client, llm, language="en-US")
    system_msg = llm.chat_calls[-1]["messages"][0]["content"]
    assert "en-US" in system_msg


# --- POST /finish (answer + LLM#2) -----------------------------------------
async def test_finish_returns_analysis_reward_streak(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await finish(client, llm, entry_id)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"analysis", "reward", "streak"}
    assert body["analysis"]["title"] == "Work Overwhelm"
    assert body["analysis"]["advice"][0]["heading"] == "Reclaim focus"
    assert body["reward"]["points_awarded"] == 20
    assert body["reward"]["points_balance"] == 20
    assert body["streak"]["current_streak"] == 1


async def test_finish_transitions_to_finished_and_appends_answer(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    await finish(client, llm, entry_id, answer="Too many meetings.")
    r = await client.get(f"{API}/entries/{entry_id}")
    body = r.json()
    assert body["status"] == "finished"
    assert body["finished_at"] is not None
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user_description", "ai_followup", "user_followup_answer"]
    assert body["messages"][2]["content"] == "Too many meetings."
    assert body["analysis"] is not None


async def test_finish_sends_structured_output_format(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    await finish(client, llm, entry_id)
    assert llm.chat_calls[-1]["response_format"]["type"] == "json_schema"


# --- finish guards ----------------------------------------------------------
async def test_double_finish_returns_already_finished(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r1 = await finish(client, llm, entry_id)
    assert r1.status_code == 200
    r2 = await finish(client, llm, entry_id)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "entry_already_finished"
    me = await client.get(f"{API}/me")
    assert me.json()["points_balance"] == 20  # not doubled


async def test_finish_unknown_entry_returns_404(client: Any, llm: Any) -> None:
    llm.set_analysis(VALID_ANALYSIS)
    missing = "11111111-1111-4111-8111-111111111111"
    r = await client.post(f"{API}/entries/{missing}/finish", json={"answer": "x"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "entry_not_found"


async def test_finish_foreign_entry_returns_404(clients: Any, llm: Any) -> None:
    owner = clients()
    other = clients()
    entry_id = await create_awaiting(owner, llm)
    llm.set_analysis(VALID_ANALYSIS)
    r = await other.post(f"{API}/entries/{entry_id}/finish", json={"answer": "x"})
    assert r.status_code == 404


# --- concurrency ------------------------------------------------------------
async def test_concurrent_finish_same_entry_awards_once(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    llm.set_analysis(VALID_ANALYSIS)  # constant -> both concurrent calls get a payload
    r1, r2 = await asyncio.gather(
        client.post(f"{API}/entries/{entry_id}/finish", json={"answer": "a"}),
        client.post(f"{API}/entries/{entry_id}/finish", json={"answer": "b"}),
    )
    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 409], f"expected one 200 and one 409, got {statuses}"
    loser = r1 if r1.status_code == 409 else r2
    assert loser.json()["error"]["code"] == "entry_already_finished"
    me = await client.get(f"{API}/me")
    assert me.json()["points_balance"] == 20


async def test_concurrent_finish_two_entries_no_lost_update(client: Any, llm: Any) -> None:
    """Two different entries of one device finished in parallel: balance = sum(ledger)."""
    e1 = await create_awaiting(client, llm)
    e2 = await create_awaiting(client, llm)
    llm.set_analysis(VALID_ANALYSIS)
    r1, r2 = await asyncio.gather(
        client.post(f"{API}/entries/{e1}/finish", json={"answer": "a"}),
        client.post(f"{API}/entries/{e2}/finish", json={"answer": "b"}),
    )
    assert r1.status_code == 200 and r2.status_code == 200
    me = await client.get(f"{API}/me")
    assert me.json()["points_balance"] == 40  # no lost update
    assert me.json()["current_streak"] == 1
