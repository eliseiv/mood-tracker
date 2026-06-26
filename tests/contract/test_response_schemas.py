"""Contract tests: responses conform to schemas in docs/04-api-contract.md."""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.catalog import ActivitiesResponse, MoodsResponse
from app.schemas.entries import (
    AnalysisOut,
    CreateEntryResponse,
    EntryResponse,
    FinishResponse,
    HistoryResponse,
)
from app.schemas.me import MeResponse, PointsResponse, StreakResponse
from tests.helpers import API, create_awaiting, entry_body, finish

pytestmark = pytest.mark.asyncio


async def test_create_entry_response_schema(client: Any, llm: Any) -> None:
    llm.set_followup("What hurt most?")
    r = await client.post(f"{API}/entries", json=entry_body(mood=4, emotions=["happy"]))
    model = CreateEntryResponse.model_validate(r.json())
    assert model.status.value == "awaiting_answer"
    assert model.prompt_version == "v1"


async def test_moods_and_activities_schema(client: Any) -> None:
    moods = await client.get(f"{API}/moods")
    MoodsResponse.model_validate(moods.json())
    acts = await client.get(f"{API}/activities")
    ActivitiesResponse.model_validate(acts.json())


async def test_me_endpoints_schema(client: Any) -> None:
    MeResponse.model_validate((await client.get(f"{API}/me")).json())
    StreakResponse.model_validate((await client.get(f"{API}/me/streak")).json())
    PointsResponse.model_validate((await client.get(f"{API}/me/points")).json())


async def test_entry_response_schema_awaiting(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    full = await client.get(f"{API}/entries/{entry_id}")
    model = EntryResponse.model_validate(full.json())
    assert model.status.value == "awaiting_answer"


async def test_finish_and_analysis_schema(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    fin = await finish(client, llm, entry_id)
    FinishResponse.model_validate(fin.json())
    analysis = await client.get(f"{API}/entries/{entry_id}/analysis")
    AnalysisOut.model_validate(analysis.json())


async def test_history_schema(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    await finish(client, llm, entry_id)
    hist = await client.get(f"{API}/entries?status=finished")
    HistoryResponse.model_validate(hist.json())


async def test_analysis_not_found_when_not_finished(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    r = await client.get(f"{API}/entries/{entry_id}/analysis")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "entry_not_found"
