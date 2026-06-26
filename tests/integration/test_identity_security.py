"""Identity scoping and baseline security."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest

from app.main import app
from tests.conftest import TEST_API_KEY
from tests.helpers import API, create_and_finish, create_awaiting

pytestmark = pytest.mark.asyncio


def _raw_client(headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    """Raw client carrying a valid API key by default (device-id under test)."""
    merged = {"X-API-Key": TEST_API_KEY}
    if headers:
        merged.update(headers)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers=merged,
    )


async def test_missing_device_id_returns_400() -> None:
    # Valid API key, no device-id -> device check is reached -> 400.
    async with _raw_client() as c:
        r = await c.get(f"{API}/me")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "device_id_required"


async def test_malformed_device_id_returns_400() -> None:
    async with _raw_client({"X-Device-Id": "not-a-uuid"}) as c:
        r = await c.get(f"{API}/me")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "device_id_invalid"


async def test_non_v4_device_id_returns_400() -> None:
    # A valid UUID but version 1, not 4.
    v1 = "time-based"
    uuid_v1 = str(uuid.uuid1())
    assert uuid.UUID(uuid_v1).version == 1, v1
    async with _raw_client({"X-Device-Id": uuid_v1}) as c:
        r = await c.get(f"{API}/me")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "device_id_invalid"


async def test_health_without_any_headers_returns_200() -> None:
    bare = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    async with bare as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_security_headers_present(client: Any) -> None:
    r = await client.get(f"{API}/me")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert r.headers["Cache-Control"] == "no-store"


async def test_foreign_entry_returns_404(clients: Any, llm: Any) -> None:
    owner = clients()
    other = clients()
    entry_id = await create_awaiting(owner, llm)
    r = await other.get(f"{API}/entries/{entry_id}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "entry_not_found"


async def test_delete_me_cascades_all_data(client: Any, llm: Any) -> None:
    entry_id, _ = await create_and_finish(client, llm)
    # custom activity too
    await client.post(f"{API}/activities", json={"label": "Pottery"})

    r = await client.delete(f"{API}/me")
    assert r.status_code == 204

    # A fresh device with the same id sees a clean profile (data gone).
    same = client  # same X-Device-Id header
    me = await same.get(f"{API}/me")
    assert me.json()["points_balance"] == 0
    assert me.json()["current_streak"] == 0
    # Old entry no longer accessible.
    r = await same.get(f"{API}/entries/{entry_id}")
    assert r.status_code == 404
