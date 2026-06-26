"""Audio upload validation: size cap, MIME allow-list and magic-bytes sniffing.

Decision rule (docs/04-api-contract.md §6.3): accept when the declared MIME is
in the allow-list OR the magic-byte signature matches a known audio container.
This avoids false 415s for iOS ``.m4a`` recordings (audio/x-m4a, audio/mp4).
"""

from __future__ import annotations

from fastapi import UploadFile

from app.core.errors import PayloadTooLargeError, UnsupportedMediaTypeError

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/aac",
        "audio/mpeg",
        "audio/wav",
        "audio/x-caf",
    }
)

_READ_CHUNK = 64 * 1024


async def read_capped(upload: UploadFile, max_bytes: int) -> bytes:
    """Read the upload fully into memory, enforcing ``max_bytes`` (-> 413)."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(
                "Audio file exceeds the maximum allowed size.",
                details={"max_bytes": max_bytes},
            )
        chunks.append(chunk)
    return b"".join(chunks)


def sniff_audio(data: bytes) -> bool:
    """Return True if ``data`` starts with a known audio container signature."""
    if len(data) < 4:
        return False
    if data[0:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WAVE":
        return True  # WAV
    if data[0:4] == b"caff":
        return True  # CAF
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return True  # MP4 / M4A container
    if data[0:3] == b"ID3":
        return True  # MP3 with ID3 tag
    if data[0] == 0xFF and len(data) >= 2:
        second = data[1]
        if (second & 0xF6) == 0xF0:
            return True  # AAC ADTS
        if (second & 0xE0) == 0xE0 and (second & 0x06) != 0:
            return True  # MP3 frame sync
    return False


def validate_audio_mime(content_type: str | None, data: bytes) -> None:
    """Raise 415 unless the declared MIME or magic-bytes signature is allowed."""
    declared = (content_type or "").split(";")[0].strip().lower()
    if declared in ALLOWED_MIME_TYPES:
        return
    if sniff_audio(data):
        return
    raise UnsupportedMediaTypeError(
        "Unsupported audio media type.",
        details={"content_type": declared or None},
    )
