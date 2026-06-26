"""ADR-008: the DB connection is not held during synchronous LLM calls."""

from __future__ import annotations

from typing import Any

import pytest

from app.db.session import get_engine
from tests.helpers import API, VALID_ANALYSIS, create_awaiting, entry_body

pytestmark = pytest.mark.asyncio


def _record_then(value: object, sink: list[int]):
    """Return a callable that records pool.checkedout() then yields ``value``."""

    def _cb() -> object:
        sink.append(get_engine().pool.checkedout())
        return value

    return _cb


async def test_no_connection_held_during_llm1(client: Any, llm: Any) -> None:
    checked: list[int] = []
    llm.set_followup(_record_then("Question?", checked))
    r = await client.post(f"{API}/entries", json=entry_body())
    assert r.status_code == 201
    assert checked == [0], f"connection held during LLM#1: {checked}"


async def test_no_connection_held_during_llm2(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(client, llm)
    checked: list[int] = []
    llm.set_analysis(_record_then(VALID_ANALYSIS, checked))
    r = await client.post(f"{API}/entries/{entry_id}/finish", json={"answer": "a"})
    assert r.status_code == 200
    assert checked == [0], f"connection held during LLM#2: {checked}"
