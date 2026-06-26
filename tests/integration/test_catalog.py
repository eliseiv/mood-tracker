"""Catalog endpoints: moods, activities, dedup."""

from __future__ import annotations

from typing import Any

import pytest

from tests.helpers import API

pytestmark = pytest.mark.asyncio


async def test_get_moods_format(client: Any) -> None:
    r = await client.get(f"{API}/moods")
    assert r.status_code == 200
    levels = r.json()["levels"]
    assert len(levels) == 5
    level = levels[0]
    assert set(level) == {"value", "code", "label", "order", "emotions"}
    assert level["value"] == 1
    emotion = level["emotions"][0]
    assert set(emotion) == {"code", "label", "order"}


async def test_get_activities_format(client: Any) -> None:
    r = await client.get(f"{API}/activities")
    assert r.status_code == 200
    activities = r.json()["activities"]
    assert len(activities) >= 1
    item = activities[0]
    assert set(item) == {"id", "code", "label", "is_custom"}
    assert item["is_custom"] is False


async def test_post_activity_creates_custom(client: Any) -> None:
    r = await client.post(f"{API}/activities", json={"label": "Pottery class"})
    assert r.status_code == 201
    body = r.json()
    assert body["label"] == "Pottery class"
    assert body["is_custom"] is True
    assert body["code"] is None
    # Appears in the listing for this device.
    listing = await client.get(f"{API}/activities")
    labels = [a["label"] for a in listing.json()["activities"]]
    assert "Pottery class" in labels


async def test_post_activity_duplicate_returns_409(client: Any) -> None:
    await client.post(f"{API}/activities", json={"label": "Pottery class"})
    # Case-insensitive dedup.
    r = await client.post(f"{API}/activities", json={"label": "pottery CLASS"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "activity_duplicate"


async def test_post_activity_empty_label_returns_422(client: Any) -> None:
    r = await client.post(f"{API}/activities", json={"label": ""})
    assert r.status_code == 422


async def test_custom_activity_is_device_scoped(clients: Any) -> None:
    owner = clients()
    other = clients()
    await owner.post(f"{API}/activities", json={"label": "Pottery class"})
    listing = await other.get(f"{API}/activities")
    labels = [a["label"] for a in listing.json()["activities"]]
    assert "Pottery class" not in labels
