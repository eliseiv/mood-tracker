"""Language selection and detection (ADR-006).

Priority for the entry language: explicit ``language`` (body) -> ``Accept-Language``
-> autodetect from text. The Whisper ``detected_language`` (ISO 639-1) is the
last-resort signal; since transcription is stateless and carries no entry field,
the server realises the "autodetect" fallback by inspecting the description text
at LLM time. Lightweight script-based heuristics (no extra dependency) cover the
common cases (en/ru/...); unknown scripts default to English.
"""

from __future__ import annotations

_DEFAULT_LANGUAGE = "en"

# Whisper verbose_json returns the full English name of the language (e.g.
# "english"); map the common ones to ISO 639-1. Unknown -> None.
_WHISPER_NAME_TO_ISO: dict[str, str] = {
    "english": "en",
    "russian": "ru",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "italian": "it",
    "portuguese": "pt",
    "dutch": "nl",
    "polish": "pl",
    "ukrainian": "uk",
    "turkish": "tr",
    "arabic": "ar",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "hindi": "hi",
}


def parse_accept_language(header: str | None) -> str | None:
    """Extract the first language tag from an Accept-Language header."""
    if not header:
        return None
    first = header.split(",")[0].strip()
    tag = first.split(";")[0].strip()
    return tag or None


def normalize_whisper_language(language: str | None) -> str | None:
    """Map a Whisper language signal to an ISO 639-1 two-letter code."""
    if not language:
        return None
    value = language.strip().lower()
    if not value:
        return None
    if len(value) == 2 and value.isalpha():
        return value
    return _WHISPER_NAME_TO_ISO.get(value)


def detect_language_from_text(text: str) -> str:
    """Best-effort script-based language autodetect; defaults to English."""
    for char in text:
        code = ord(char)
        if 0x0400 <= code <= 0x04FF:  # Cyrillic
            return "ru"
        if 0x4E00 <= code <= 0x9FFF:  # CJK unified ideographs
            return "zh"
        if 0x3040 <= code <= 0x30FF:  # Hiragana / Katakana
            return "ja"
        if 0xAC00 <= code <= 0xD7A3:  # Hangul
            return "ko"
        if 0x0600 <= code <= 0x06FF:  # Arabic
            return "ar"
    return _DEFAULT_LANGUAGE


def resolve_entry_language(body_language: str | None, accept_language: str | None) -> str | None:
    """Resolve the entry language at creation time (no text yet).

    Returns ``None`` when neither an explicit language nor Accept-Language is
    present; the autodetect fallback is applied later when text is available.
    """
    if body_language:
        return body_language
    return parse_accept_language(accept_language)


def ensure_language(entry_language: str | None, *texts: str) -> str:
    """Return the effective LLM language, autodetecting from text if needed."""
    if entry_language:
        return entry_language
    for text in texts:
        if text and text.strip():
            return detect_language_from_text(text)
    return _DEFAULT_LANGUAGE
