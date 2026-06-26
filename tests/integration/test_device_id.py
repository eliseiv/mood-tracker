"""Opaque string X-Device-Id (ADR-007, iteration 8): validation, echo, scope."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest

from app.main import app
from tests.conftest import TEST_API_KEY
from tests.helpers import API, VALID_ANALYSIS, create_awaiting, finish

pytestmark = pytest.mark.asyncio


def _client(device_id: str | None) -> httpx.AsyncClient:
    headers = {"X-API-Key": TEST_API_KEY}
    if device_id is not None:
        headers["X-Device-Id"] = device_id
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers
    )


# --- Validation: required ---------------------------------------------------
@pytest.mark.parametrize("value", [None, "", "   ", "\t  "])
async def test_missing_or_blank_device_id_returns_400_required(value: str | None) -> None:
    async with _client(value) as c:
        r = await c.get(f"{API}/me")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "device_id_required"


# --- Validation: too long / bad charset ------------------------------------
async def test_device_id_over_64_chars_returns_400_invalid() -> None:
    async with _client("a" * 65) as c:
        r = await c.get(f"{API}/me")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "device_id_invalid"


async def test_device_id_exactly_64_chars_is_valid() -> None:
    async with _client("a" * 64) as c:
        r = await c.get(f"{API}/me")
    assert r.status_code == 200


@pytest.mark.parametrize("value", ["a b", "bad!", "semi;colon", "slash/x", "with space"])
async def test_invalid_charset_returns_400_invalid(value: str) -> None:
    async with _client(value) as c:
        r = await c.get(f"{API}/me")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "device_id_invalid"


@pytest.mark.parametrize("text", ["юзер", "ユーザー", "用户", "über", "café"])
async def test_non_ascii_utf8_bytes_device_id_returns_400(text: str) -> None:
    # A real client cannot put non-latin-1 chars in an HTTP header; sending the
    # UTF-8 bytes makes the server decode them latin-1 (mojibake) -> 400 invalid.
    headers = {"X-API-Key": TEST_API_KEY, "X-Device-Id": text.encode("utf-8")}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get(f"{API}/me", headers=headers)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "device_id_invalid"


@pytest.mark.parametrize("value", ["a-b_c.d", "TestUser", "user.name-1_2", "ABCdef123", "----"])
async def test_allowed_charset_passes(value: str) -> None:
    async with _client(value) as c:
        r = await c.get(f"{API}/me")
    assert r.status_code == 200
    assert r.json()["device_id"] == value


async def test_uuid_device_id_still_valid() -> None:
    did = str(uuid.uuid4())
    async with _client(did) as c:
        r = await c.get(f"{API}/me")
    assert r.status_code == 200
    assert r.json()["device_id"] == did


# --- Echo verbatim + trim ---------------------------------------------------
async def test_device_id_is_trimmed_and_echoed_verbatim() -> None:
    async with _client("  testuser  ") as c:
        r = await c.get(f"{API}/me")
    assert r.status_code == 200
    assert r.json()["device_id"] == "testuser"


# --- Case sensitivity: distinct devices, isolated scope ---------------------
async def test_case_sensitive_devices_are_isolated(llm: Any) -> None:
    lower = _client("testuser")
    upper = _client("TestUser")
    async with lower, upper:
        # Create a custom activity under the lowercase device only.
        created = await lower.post(f"{API}/activities", json={"label": "Pottery class"})
        assert created.status_code == 201

        lower_list = (await lower.get(f"{API}/activities")).json()["activities"]
        upper_list = (await upper.get(f"{API}/activities")).json()["activities"]
    lower_labels = [a["label"] for a in lower_list]
    upper_labels = [a["label"] for a in upper_list]
    assert "Pottery class" in lower_labels
    assert "Pottery class" not in upper_labels  # different scope


# --- Full lifecycle with a readable string device id ------------------------
async def test_full_lifecycle_with_string_device_id(llm: Any) -> None:
    client = _client("testuser")
    async with client:
        entry_id = await create_awaiting(client, llm)
        fin = await finish(client, llm, entry_id)
        assert fin.status_code == 200
        assert fin.json()["reward"]["points_awarded"] == 20
        assert fin.json()["streak"]["current_streak"] == 1

        history = await client.get(f"{API}/entries?status=finished")
        assert entry_id in [it["id"] for it in history.json()["items"]]
        me = await client.get(f"{API}/me")
        assert me.json()["device_id"] == "testuser"
        assert me.json()["points_balance"] == 20


async def test_foreign_entry_404_across_string_devices(llm: Any) -> None:
    owner = _client("owneruser")
    other = _client("otheruser")
    async with owner, other:
        entry_id = await create_awaiting(owner, llm)
        r = await other.get(f"{API}/entries/{entry_id}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "entry_not_found"


async def test_finish_foreign_entry_404_across_string_devices(llm: Any) -> None:
    owner = _client("owner2")
    other = _client("other2")
    async with owner, other:
        entry_id = await create_awaiting(owner, llm)
        llm.set_analysis(VALID_ANALYSIS)
        r = await other.post(f"{API}/entries/{entry_id}/finish", json={"answer": "x"})
    assert r.status_code == 404
