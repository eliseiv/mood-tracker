"""Gamification: points award, balance = ledger sum, streak progression."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select

from app.db.models import PointsLedger
from app.db.session import get_sessionmaker
from tests.conftest import Clock
from tests.helpers import API, create_and_finish

pytestmark = pytest.mark.asyncio


async def _ledger_sum(device_id: str) -> int:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return await session.scalar(
            select(func.coalesce(func.sum(PointsLedger.delta), 0)).where(
                PointsLedger.device_id == device_id
            )
        )


async def test_finish_awards_exactly_points_per_entry(client: Any, llm: Any) -> None:
    _, r = await create_and_finish(client, llm)
    assert r.json()["reward"]["points_awarded"] == 20
    assert r.json()["reward"]["points_balance"] == 20
    points = await client.get(f"{API}/me/points")
    assert points.json()["points_per_entry"] == 20


async def test_points_balance_equals_ledger_sum(client: Any, llm: Any, clock: Clock) -> None:
    clock.set(datetime(2026, 6, 26, 12, 0, tzinfo=UTC))
    await create_and_finish(client, llm)
    clock.set(datetime(2026, 6, 27, 12, 0, tzinfo=UTC))
    await create_and_finish(client, llm)

    balance = (await client.get(f"{API}/me")).json()["points_balance"]
    assert balance == 40
    assert await _ledger_sum(client.device_id) == balance


async def test_streak_progression_continue_break(client: Any, llm: Any, clock: Clock) -> None:
    clock.set(datetime(2026, 6, 26, 12, 0, tzinfo=UTC))
    _, r = await create_and_finish(client, llm)
    assert r.json()["streak"]["current_streak"] == 1

    clock.set(datetime(2026, 6, 27, 12, 0, tzinfo=UTC))  # consecutive
    _, r = await create_and_finish(client, llm)
    assert r.json()["streak"]["current_streak"] == 2
    assert r.json()["streak"]["longest_streak"] == 2

    clock.set(datetime(2026, 6, 30, 12, 0, tzinfo=UTC))  # gap
    _, r = await create_and_finish(client, llm)
    assert r.json()["streak"]["current_streak"] == 1
    assert r.json()["streak"]["longest_streak"] == 2


async def test_multiple_entries_same_day_streak_unchanged(
    client: Any, llm: Any, clock: Clock
) -> None:
    clock.set(datetime(2026, 6, 26, 9, 0, tzinfo=UTC))
    _, r = await create_and_finish(client, llm)
    assert r.json()["streak"]["current_streak"] == 1

    clock.set(datetime(2026, 6, 26, 20, 0, tzinfo=UTC))
    _, r = await create_and_finish(client, llm)
    assert r.json()["streak"]["current_streak"] == 1
    me = await client.get(f"{API}/me")
    assert me.json()["points_balance"] == 40  # points still accrue per entry
