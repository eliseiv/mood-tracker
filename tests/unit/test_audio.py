"""Unit tests for audio validation (size cap, MIME allow-list, magic bytes)."""

from __future__ import annotations

import pytest

from app.api.audio import sniff_audio, validate_audio_mime
from app.core.errors import UnsupportedMediaTypeError

WAV = b"RIFF\x00\x00\x00\x00WAVEfmt "
MP4 = b"\x00\x00\x00\x18ftypM4A "
MP3_ID3 = b"ID3\x03\x00\x00\x00"
CAF = b"caff\x00\x01\x00\x00"


@pytest.mark.parametrize("data", [WAV, MP4, MP3_ID3, CAF])
def test_sniff_audio_recognises_containers(data: bytes) -> None:
    assert sniff_audio(data) is True


def test_sniff_audio_rejects_non_audio() -> None:
    assert sniff_audio(b"hello there, not audio") is False
    assert sniff_audio(b"ab") is False  # too short


def test_validate_mime_accepts_allowlisted_header() -> None:
    # iOS AVFoundation MIME types must pass even with non-audio bytes.
    validate_audio_mime("audio/x-m4a", b"garbage")
    validate_audio_mime("audio/mp4", b"garbage")


def test_validate_mime_accepts_by_signature_when_header_unknown() -> None:
    validate_audio_mime("application/octet-stream", WAV)


def test_validate_mime_rejects_unknown_header_and_signature() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        validate_audio_mime("text/plain", b"hello there, not audio")
