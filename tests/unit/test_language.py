"""Unit tests for language selection / detection (ADR-006)."""

from __future__ import annotations

import pytest

from app.llm.language import (
    detect_language_from_text,
    ensure_language,
    normalize_whisper_language,
    parse_accept_language,
    resolve_entry_language,
)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, None),
        ("", None),
        ("en-US,en;q=0.9", "en-US"),
        ("ru-RU", "ru-RU"),
    ],
)
def test_parse_accept_language(header: str | None, expected: str | None) -> None:
    assert parse_accept_language(header) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("en", "en"),
        ("RU", "ru"),
        ("english", "en"),
        ("russian", "ru"),
        ("klingon", None),
    ],
)
def test_normalize_whisper_language(value: str | None, expected: str | None) -> None:
    assert normalize_whisper_language(value) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello world", "en"),
        ("привет мир", "ru"),
        ("你好世界", "zh"),
        ("こんにちは", "ja"),
        ("안녕하세요", "ko"),
        ("مرحبا", "ar"),
    ],
)
def test_detect_language_from_text(text: str, expected: str) -> None:
    assert detect_language_from_text(text) == expected


def test_resolve_entry_language_priority() -> None:
    assert resolve_entry_language("fr-FR", "en-US") == "fr-FR"
    assert resolve_entry_language(None, "en-US,en") == "en-US"
    assert resolve_entry_language(None, None) is None


def test_ensure_language_uses_entry_then_autodetect() -> None:
    assert ensure_language("en-US", "anything") == "en-US"
    assert ensure_language(None, "привет") == "ru"
    assert ensure_language(None, "", "  ") == "en"
