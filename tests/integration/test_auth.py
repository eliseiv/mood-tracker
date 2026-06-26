"""App-level X-API-Key authentication (ADR-009), checked before X-Device-Id."""

from __future__ import annotations

import logging
import uuid

import httpx
import pytest
from sqlalchemy import func, select

from app.db.models import Device
from app.db.session import get_sessionmaker
from app.main import app
from tests.conftest import TEST_API_KEY

pytestmark = pytest.mark.asyncio

_VALID_DEVICE = str(uuid.uuid4())


def _client(headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers or {}
    )


async def _device_count(device_id: str) -> int:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return await session.scalar(
            select(func.count()).select_from(Device).where(Device.id == uuid.UUID(device_id))
        )


# --- Missing / invalid key --------------------------------------------------
async def test_missing_api_key_returns_401_no_details() -> None:
    async with _client({"X-Device-Id": _VALID_DEVICE}) as c:
        r = await c.get("/api/v1/me")
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "api_key_required"
    assert "details" not in err


async def test_invalid_api_key_returns_401() -> None:
    headers = {"X-Device-Id": _VALID_DEVICE, "X-API-Key": "wrong-key"}
    async with _client(headers) as c:
        r = await c.get("/api/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "api_key_invalid"


# --- Key is checked BEFORE device-id; no Device is created on auth failure ---
async def test_missing_key_and_missing_device_id_is_401_no_device() -> None:
    async with _client() as c:  # neither header
        r = await c.get("/api/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "api_key_required"


async def test_invalid_key_with_bad_device_id_is_401_no_device_created() -> None:
    device_id = str(uuid.uuid4())
    headers = {"X-API-Key": "nope", "X-Device-Id": "not-a-uuid"}
    async with _client(headers) as c:
        r = await c.get("/api/v1/me")
    assert r.status_code == 401  # key checked first, before device validation
    assert r.json()["error"]["code"] == "api_key_invalid"
    # The middleware short-circuits before any Device upsert.
    assert await _device_count(device_id) == 0


# --- Valid key, then device-id rules apply ---------------------------------
async def test_valid_key_missing_device_id_returns_400() -> None:
    async with _client({"X-API-Key": TEST_API_KEY}) as c:
        r = await c.get("/api/v1/me")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "device_id_required"


async def test_valid_key_invalid_device_id_returns_400() -> None:
    headers = {"X-API-Key": TEST_API_KEY, "X-Device-Id": "not-a-uuid"}
    async with _client(headers) as c:
        r = await c.get("/api/v1/me")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "device_id_invalid"


async def test_valid_key_and_device_id_succeeds() -> None:
    device_id = str(uuid.uuid4())
    headers = {"X-API-Key": TEST_API_KEY, "X-Device-Id": device_id}
    async with _client(headers) as c:
        r = await c.get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["device_id"] == device_id


async def test_health_needs_no_headers() -> None:
    async with _client() as c:
        r = await c.get("/health")
    assert r.status_code == 200


# --- Key must never leak into logs -----------------------------------------
async def test_api_key_not_leaked_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    device_id = str(uuid.uuid4())
    headers = {"X-API-Key": TEST_API_KEY, "X-Device-Id": device_id}
    with caplog.at_level(logging.DEBUG):
        async with _client(headers) as c:
            await c.get("/api/v1/me")
            await c.get("/api/v1/moods")
    blob = "\n".join(
        [rec.getMessage() for rec in caplog.records] + [str(rec.__dict__) for rec in caplog.records]
    )
    assert TEST_API_KEY not in blob
