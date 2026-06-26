"""Transcription endpoint: size cap, MIME allow-list, success."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tests.helpers import API

pytestmark = pytest.mark.asyncio

WAV = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 16


async def test_file_over_10mb_returns_413(client: Any, llm: Any) -> None:
    big = b"\x00" * (10 * 1024 * 1024 + 100)
    r = await client.post(f"{API}/transcriptions", files={"audio": ("big.m4a", big, "audio/m4a")})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"


async def test_unsupported_mime_without_signature_returns_415(client: Any, llm: Any) -> None:
    r = await client.post(
        f"{API}/transcriptions",
        files={"audio": ("note.txt", b"hello there, not audio", "text/plain")},
    )
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_media_type"


@pytest.mark.parametrize("mime", ["audio/x-m4a", "audio/mp4"])
async def test_ios_m4a_mime_passes(client: Any, llm: Any, mime: str) -> None:
    llm.set_transcription(SimpleNamespace(text="hello from iOS", language="english"))
    r = await client.post(f"{API}/transcriptions", files={"audio": ("rec.m4a", b"\x00" * 64, mime)})
    assert r.status_code == 200
    assert r.json()["text"] == "hello from iOS"
    assert r.json()["detected_language"] == "en"  # ISO 639-1


async def test_success_returns_text_and_iso_language(client: Any, llm: Any) -> None:
    llm.set_transcription(SimpleNamespace(text="привет", language="ru"))
    r = await client.post(f"{API}/transcriptions", files={"audio": ("rec.wav", WAV, "audio/wav")})
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "привет"
    assert body["detected_language"] == "ru"
