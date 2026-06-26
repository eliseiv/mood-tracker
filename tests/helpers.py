"""Reusable flow helpers for the 2-POST entry lifecycle (ADR-003)."""

from __future__ import annotations

import json
from typing import Any

import httpx

API = "/api/v1"

VALID_ANALYSIS = json.dumps(
    {
        "title": "Work Overwhelm",
        "overview": "A demanding workday left you drained and unfocused.",
        "advice": [
            {"heading": "Reclaim focus", "body": "Block a no-meeting slot tomorrow."},
            {"heading": "Decompress", "body": "Take a short walk before bed."},
        ],
    }
)


def over_limit_analysis() -> str:
    """Analysis JSON that violates the length limits (title>3, overview>40)."""
    return json.dumps(
        {
            "title": "This Title Has Way Too Many Words Indeed",
            "overview": " ".join(f"word{i}" for i in range(60)),
            "advice": [{"heading": "H", "body": "B"}],
        }
    )


def entry_body(
    *,
    mood: int = 2,
    emotions: list[str] | None = None,
    activities: list[str] | None = None,
    description: str = "I had a rough day at work and felt overwhelmed.",
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "mood": mood,
        "emotions": emotions if emotions is not None else ["sad", "tired"],
        "description": description,
    }
    if activities is not None:
        body["activities"] = activities
    body.update(extra)
    return body


async def first_activity_id(client: httpx.AsyncClient) -> str:
    resp = await client.get(f"{API}/activities")
    return resp.json()["activities"][0]["id"]


async def create_awaiting(
    client: httpx.AsyncClient,
    llm: Any,
    *,
    question: str = "What part of work felt heaviest today?",
    **body: Any,
) -> str:
    """POST /entries with LLM#1 mocked; return the entry id (status awaiting_answer)."""
    llm.set_followup(question)
    resp = await client.post(f"{API}/entries", json=entry_body(**body))
    assert resp.status_code == 201, resp.text
    return resp.json()["entry_id"]


async def finish(
    client: httpx.AsyncClient,
    llm: Any,
    entry_id: str,
    *,
    analysis: Any = VALID_ANALYSIS,
    answer: str = "Too many meetings, no focus time.",
) -> httpx.Response:
    """POST /finish with LLM#2 mocked; return the response."""
    llm.set_analysis(analysis)
    return await client.post(f"{API}/entries/{entry_id}/finish", json={"answer": answer})


async def create_and_finish(
    client: httpx.AsyncClient, llm: Any, **body: Any
) -> tuple[str, httpx.Response]:
    """Drive a fresh entry all the way to finished; return (entry_id, finish response)."""
    entry_id = await create_awaiting(client, llm, **body)
    resp = await finish(client, llm, entry_id)
    return entry_id, resp
