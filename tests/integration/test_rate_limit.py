"""Rate limiting keyed by device-id + client IP (docs/05-security.md).

Expensive LLM/STT routes are additionally IP-limited so rotating the
client-controlled device-id from one IP cannot bypass the limit. Default GET
reads are device-limited only (not IP-limited).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.core.rate_limit import MemoryRateLimiter
from app.main import app
from tests.helpers import API, entry_body

pytestmark = pytest.mark.asyncio

_LIMIT = 3


@pytest.fixture
def small_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fresh limiter + tiny limit for every category."""
    monkeypatch.setattr(app.state, "rate_limiter", MemoryRateLimiter())
    monkeypatch.setattr("app.api.deps.limits_for", lambda category, settings: (_LIMIT, 60))


async def test_entries_ip_limited_across_device_rotation(
    clients: Any, llm: Any, small_limits: None
) -> None:
    """Rotating device-id from one IP on POST /entries trips the IP limit -> 429."""
    llm.set_followup("ok?")
    statuses = []
    for _ in range(_LIMIT + 1):
        c = clients()  # new device-id each time, same IP (127.0.0.1)
        r = await c.post(f"{API}/entries", json=entry_body())
        statuses.append(r.status_code)
    assert statuses[:_LIMIT] == [201] * _LIMIT
    assert statuses[_LIMIT] == 429
    # last response carries Retry-After
    last = await clients().post(f"{API}/entries", json=entry_body())
    assert last.status_code == 429
    assert "Retry-After" in last.headers


async def test_finish_ip_limited_across_device_rotation(
    clients: Any, llm: Any, small_limits: None
) -> None:
    """finish is llm-category -> IP-limited; rotating device-id still trips 429."""
    # Each finish needs an existing awaiting entry; create them first (this also
    # consumes the llm IP budget), so just assert a 429 surfaces under rotation.
    seen_429 = False
    for _ in range(_LIMIT + 2):
        c = clients()
        missing = uuid.uuid4()
        llm.set_analysis("x")
        r = await c.post(f"{API}/entries/{missing}/finish", json={"answer": "a"})
        if r.status_code == 429:
            seen_429 = True
            assert "Retry-After" in r.headers
            break
    assert seen_429


async def test_default_get_not_ip_limited(clients: Any, small_limits: None) -> None:
    """GET /activities (default category) is device-limited only, not IP-limited."""
    statuses = []
    for _ in range(_LIMIT + 3):
        c = clients()  # rotate device-id, same IP
        r = await c.get(f"{API}/activities")
        statuses.append(r.status_code)
    assert all(s == 200 for s in statuses), statuses
