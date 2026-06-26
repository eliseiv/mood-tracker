"""Endpoints removed by the 2-POST redesign must no longer be routable."""

from __future__ import annotations

from typing import Any

import pytest

from tests.helpers import API

pytestmark = pytest.mark.asyncio

_ENTRY = "11111111-1111-4111-8111-111111111111"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("patch", f"{API}/entries/{_ENTRY}/mood"),
        ("patch", f"{API}/entries/{_ENTRY}/activities"),
        ("post", f"{API}/entries/{_ENTRY}/description"),
        ("post", f"{API}/entries/{_ENTRY}/followup"),
        ("post", f"{API}/entries/{_ENTRY}/followup/answer"),
    ],
)
async def test_removed_granular_routes_are_gone(client: Any, method: str, path: str) -> None:
    r = await client.request(method, path, json={})
    assert r.status_code in (404, 405), f"{method} {path} -> {r.status_code}"


async def test_patch_on_entry_resource_is_method_not_allowed(client: Any) -> None:
    # /entries/{id} exists only for GET now; PATCH must be 405.
    r = await client.patch(f"{API}/entries/{_ENTRY}", json={})
    assert r.status_code == 405
