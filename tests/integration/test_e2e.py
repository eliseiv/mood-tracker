"""End-to-end user journey through the full stack with enforced X-API-Key.

Drives the complete 2-POST journey (auth -> identity -> rate-limit -> three-phase
LLM POSTs) against the real ASGI app with mocked OpenAI/Whisper, and asserts data
connectivity across steps (entry_id, points, streak, history).
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIError, APITimeoutError

from app.main import app
from tests.conftest import Clock
from tests.helpers import API, VALID_ANALYSIS, entry_body

pytestmark = pytest.mark.asyncio

_REQ = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
WAV = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 16


async def test_full_happy_path_journey(client: Any, llm: Any, clock: Clock) -> None:
    clock.set(datetime(2026, 6, 26, 12, 0, tzinfo=UTC))
    device_id = client.device_id

    # 1) GET /me — device is created on first access.
    me = await client.get(f"{API}/me")
    assert me.status_code == 200
    assert me.json()["device_id"] == device_id
    assert me.json()["points_balance"] == 0
    assert me.json()["current_streak"] == 0

    # 2) Catalog.
    moods = await client.get(f"{API}/moods")
    assert moods.status_code == 200 and len(moods.json()["levels"]) == 5
    activities = await client.get(f"{API}/activities")
    assert activities.status_code == 200

    # 3) Custom activity.
    created = await client.post(f"{API}/activities", json={"label": "Pottery class"})
    assert created.status_code == 201
    activity_id = created.json()["id"]

    # 4) Transcription (mock Whisper).
    llm.set_transcription(SimpleNamespace(text="I had a rough day at work.", language="english"))
    tr = await client.post(
        f"{API}/transcriptions", files={"audio": ("rec.wav", WAV, "audio/wav")}
    )
    assert tr.status_code == 200
    transcript = tr.json()["text"]
    assert tr.json()["detected_language"] == "en"

    # 5) POST /entries (create + LLM#1) using the transcript as the description.
    llm.set_followup("What part of work felt heaviest today?")
    create = await client.post(
        f"{API}/entries",
        json=entry_body(
            mood=2,
            emotions=["sad", "tired"],
            activities=[activity_id],
            description=transcript,
            source="voice",
            language="en-US",
            timezone="Europe/Amsterdam",
        ),
    )
    assert create.status_code == 201
    body = create.json()
    assert body["status"] == "awaiting_answer"
    assert body["question"] == "What part of work felt heaviest today?"
    assert body["prompt_version"] == "v1"
    entry_id = body["entry_id"]

    # 6) POST /finish (answer + LLM#2).
    llm.set_analysis(VALID_ANALYSIS)
    fin = await client.post(
        f"{API}/entries/{entry_id}/finish", json={"answer": "Too many meetings."}
    )
    assert fin.status_code == 200
    fbody = fin.json()
    assert fbody["analysis"]["title"] == "Work Overwhelm"
    assert fbody["reward"]["points_awarded"] == 20
    assert fbody["reward"]["points_balance"] == 20
    assert fbody["streak"]["current_streak"] == 1

    # 7) History.
    history = await client.get(f"{API}/entries?status=finished")
    assert history.status_code == 200
    ids = [it["id"] for it in history.json()["items"]]
    assert entry_id in ids

    # 8) Full entry + analysis.
    full = await client.get(f"{API}/entries/{entry_id}")
    assert full.status_code == 200
    assert full.json()["status"] == "finished"
    roles = [m["role"] for m in full.json()["messages"]]
    assert roles == ["user_description", "ai_followup", "user_followup_answer"]
    analysis = await client.get(f"{API}/entries/{entry_id}/analysis")
    assert analysis.status_code == 200
    assert analysis.json()["title"] == "Work Overwhelm"

    # 9) GET /me reflects the awarded points/streak and upserted tz/locale.
    me2 = await client.get(f"{API}/me")
    assert me2.json()["points_balance"] == 20
    assert me2.json()["current_streak"] == 1
    assert me2.json()["timezone"] == "Europe/Amsterdam"
    assert me2.json()["language"] == "en-US"
    assert me2.json()["last_entry_date"] == "2026-06-26"


# --- E2E negative: auth enforced on every step -----------------------------
def _client(headers: dict[str, str]) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers
    )


_DEVICE = "11111111-1111-4111-8111-111111111111"
_ENTRY = "22222222-2222-4222-8222-222222222222"
_JOURNEY = [
    ("get", f"{API}/me"),
    ("get", f"{API}/moods"),
    ("get", f"{API}/activities"),
    ("post", f"{API}/activities"),
    ("post", f"{API}/entries"),
    ("post", f"{API}/entries/{_ENTRY}/finish"),
    ("get", f"{API}/entries"),
    ("get", f"{API}/entries/{_ENTRY}/analysis"),
]


@pytest.mark.parametrize(("method", "path"), _JOURNEY)
async def test_journey_without_api_key_is_401(method: str, path: str) -> None:
    async with _client({"X-Device-Id": _DEVICE}) as c:
        r = await c.request(method, path, json={})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "api_key_required"


@pytest.mark.parametrize(("method", "path"), _JOURNEY)
async def test_journey_with_wrong_api_key_is_401(method: str, path: str) -> None:
    async with _client({"X-Device-Id": _DEVICE, "X-API-Key": "bad"}) as c:
        r = await c.request(method, path, json={})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "api_key_invalid"


# --- E2E negative: forbidden transition + LLM failure with retry -----------
async def test_double_finish_is_conflict(client: Any, llm: Any) -> None:
    llm.set_followup("q?")
    create = await client.post(f"{API}/entries", json=entry_body())
    entry_id = create.json()["entry_id"]
    llm.set_analysis(VALID_ANALYSIS)
    r1 = await client.post(f"{API}/entries/{entry_id}/finish", json={"answer": "a"})
    assert r1.status_code == 200
    r2 = await client.post(f"{API}/entries/{entry_id}/finish", json={"answer": "a"})
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "entry_already_finished"


async def test_llm1_failure_then_retry_succeeds(client: Any, llm: Any) -> None:
    # LLM#1 fails -> 502, no entry; retry with same body succeeds.
    llm.set_followup(APIError("boom", request=_REQ, body=None))
    fail = await client.post(f"{API}/entries", json=entry_body())
    assert fail.status_code == 502
    history = await client.get(f"{API}/entries?status=finished")
    assert history.json()["items"] == []

    llm.set_followup("Recovered question?")
    ok = await client.post(f"{API}/entries", json=entry_body())
    assert ok.status_code == 201
    assert ok.json()["status"] == "awaiting_answer"


async def test_llm2_failure_keeps_status_then_retry_succeeds(client: Any, llm: Any) -> None:
    llm.set_followup("q?")
    create = await client.post(f"{API}/entries", json=entry_body())
    entry_id = create.json()["entry_id"]

    # LLM#2 unavailable -> 503, status unchanged.
    llm.set_analysis(APITimeoutError(request=_REQ))
    fail = await client.post(f"{API}/entries/{entry_id}/finish", json={"answer": "a"})
    assert fail.status_code == 503
    state = await client.get(f"{API}/entries/{entry_id}")
    assert state.json()["status"] == "awaiting_answer"

    # Retry the same step succeeds.
    llm.set_analysis(VALID_ANALYSIS)
    ok = await client.post(f"{API}/entries/{entry_id}/finish", json={"answer": "a"})
    assert ok.status_code == 200
    assert ok.json()["reward"]["points_awarded"] == 20
