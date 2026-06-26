"""History endpoint: cursor pagination, ordering, validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.conftest import Clock
from tests.helpers import API, create_and_finish

pytestmark = pytest.mark.asyncio


async def _finish_n(client: Any, llm: Any, clock: Clock, n: int) -> list[str]:
    """Finish n entries at strictly increasing finished_at; return ids in finish order."""
    base = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    ids: list[str] = []
    for i in range(n):
        clock.set(base + timedelta(days=i))
        entry_id, _ = await create_and_finish(client, llm)
        ids.append(entry_id)
    return ids


async def test_history_orders_finished_at_desc(client: Any, llm: Any, clock: Clock) -> None:
    ids = await _finish_n(client, llm, clock, 3)
    r = await client.get(f"{API}/entries?status=finished")
    items = r.json()["items"]
    assert [it["id"] for it in items] == list(reversed(ids))
    assert r.json()["next_cursor"] is None
    # Item shape.
    assert set(items[0]) == {"id", "mood", "emotions", "title", "finished_at"}


async def test_history_cursor_pagination(client: Any, llm: Any, clock: Clock) -> None:
    ids = await _finish_n(client, llm, clock, 3)
    expected = list(reversed(ids))

    r1 = await client.get(f"{API}/entries?status=finished&limit=2")
    page1 = r1.json()
    assert [it["id"] for it in page1["items"]] == expected[:2]
    assert page1["next_cursor"] is not None

    r2 = await client.get(f"{API}/entries?status=finished&limit=2&cursor={page1['next_cursor']}")
    page2 = r2.json()
    assert [it["id"] for it in page2["items"]] == expected[2:]
    assert page2["next_cursor"] is None


async def test_history_empty_has_null_cursor(client: Any) -> None:
    r = await client.get(f"{API}/entries?status=finished")
    assert r.json()["items"] == []
    assert r.json()["next_cursor"] is None


async def test_history_invalid_cursor_returns_422(client: Any) -> None:
    r = await client.get(f"{API}/entries?status=finished&cursor=%%%not-base64%%%")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_history_limit_over_50_returns_422(client: Any) -> None:
    r = await client.get(f"{API}/entries?status=finished&limit=51")
    assert r.status_code == 422


async def test_history_unsupported_status_returns_422(client: Any) -> None:
    r = await client.get(f"{API}/entries?status=draft")
    assert r.status_code == 422
