"""Timezone upsert (REWORK-2) and streak by local date (2-POST flow)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from tests.conftest import Clock
from tests.helpers import API, create_awaiting, entry_body, finish

pytestmark = pytest.mark.asyncio


async def test_post_entries_upserts_timezone_and_locale(client: Any, llm: Any) -> None:
    await create_awaiting(client, llm, timezone="Europe/Amsterdam", language="en-US")
    me = (await client.get(f"{API}/me")).json()
    assert me["timezone"] == "Europe/Amsterdam"
    assert me["language"] == "en-US"


async def test_invalid_timezone_ignored_no_422_and_not_overwritten(client: Any, llm: Any) -> None:
    await create_awaiting(client, llm, timezone="Europe/Amsterdam")
    # Invalid zone must be ignored: 201, stored value kept, no error.
    llm.set_followup("ok?")
    r = await client.post(f"{API}/entries", json=entry_body(timezone="Mars/Phobos"))
    assert r.status_code == 201
    me = (await client.get(f"{API}/me")).json()
    assert me["timezone"] == "Europe/Amsterdam"


async def test_streak_local_date_differs_by_timezone(clients: Any, llm: Any, clock: Clock) -> None:
    """Same UTC instant near midnight yields different local dates per timezone."""
    # 2026-06-26 15:30 UTC -> Tokyo is 2026-06-27, UTC is 2026-06-26.
    clock.set(datetime(2026, 6, 26, 15, 30, tzinfo=UTC))

    tokyo = clients()
    utc = clients()

    tokyo_id = await create_awaiting(tokyo, llm, timezone="Asia/Tokyo")
    await finish(tokyo, llm, tokyo_id)

    utc_id = await create_awaiting(utc, llm)  # no timezone -> UTC
    await finish(utc, llm, utc_id)

    tokyo_me = (await tokyo.get(f"{API}/me")).json()
    utc_me = (await utc.get(f"{API}/me")).json()
    assert tokyo_me["last_entry_date"] == "2026-06-27"
    assert utc_me["last_entry_date"] == "2026-06-26"
