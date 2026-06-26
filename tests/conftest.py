"""Shared test fixtures.

Environment is configured *before* any ``app`` import so the cached
``get_settings()`` / engine singletons bind to the test SQLite file. OpenAI is
always faked (see ``llm`` fixture) — no real network calls ever happen.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# --- Environment must be set before importing the application ----------------
# App-level API key auth (ADR-009) is enforced in the test environment so every
# /api/v1/* client sends X-API-Key. APP_ENV stays local (default).
TEST_API_KEY = "test-secret-api-key-3f9c1a"

_TEST_DB = Path(__file__).resolve().parent.parent / "test_mood.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ENVIRONMENT"] = "test"
os.environ["API_KEY"] = TEST_API_KEY
os.environ.pop("APP_ENV", None)  # default -> local
# Disable rate limiting as a test-flakiness source (not under test here).
os.environ["RATE_LIMIT_DEFAULT_MAX"] = "100000"
os.environ["RATE_LIMIT_LLM_MAX"] = "100000"
os.environ["RATE_LIMIT_TRANSCRIPTION_MAX"] = "100000"

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.main import app  # noqa: E402

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Database lifecycle (migrations applied per docs/06-testing-strategy.md)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    """Create a fresh test DB and apply Alembic migrations (schema + seed)."""
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_PROJECT_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield
    if _TEST_DB.exists():
        with contextlib.suppress(PermissionError):
            _TEST_DB.unlink()


@pytest_asyncio.fixture(autouse=True)
async def _clean_dynamic_tables() -> AsyncIterator[None]:
    """Truncate per-device data between tests; catalog (seed) is preserved."""
    yield
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # Deleting devices cascades to entries, messages, analysis, advice,
        # ledger and custom activities (FK ON). Global catalog stays.
        await session.execute(text("DELETE FROM devices"))
        await session.commit()


# ---------------------------------------------------------------------------
# Fake OpenAI client (no real calls)
# ---------------------------------------------------------------------------
def _chat_response(content: str | None) -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class LLMController:
    """Per-test controller for the fake OpenAI client behaviour."""

    def __init__(self) -> None:
        self.followup: Any = None  # str | Exception | None
        self._analysis: Any = None  # str | list | Exception | None
        self.transcription: Any = None  # SimpleNamespace | Exception | None
        self.chat_calls: list[dict[str, Any]] = []
        self.transcribe_calls: list[dict[str, Any]] = []

    # configuration helpers -------------------------------------------------
    def set_followup(self, value: Any) -> None:
        self.followup = value

    def set_analysis(self, value: Any) -> None:
        """str -> constant; list -> sequential queue; Exception -> always raise."""
        self._analysis = list(value) if isinstance(value, list) else value

    def set_transcription(self, value: Any) -> None:
        self.transcription = value

    # fake transport --------------------------------------------------------
    async def _chat(self, **kwargs: Any) -> Any:
        self.chat_calls.append(kwargs)
        is_analysis = "response_format" in kwargs
        value = self._analysis if is_analysis else self.followup
        if isinstance(value, list):
            if not value:
                raise AssertionError("analysis queue exhausted")
            value = value.pop(0)
        # A callable observes call-time state (e.g. pool checkedout) and returns
        # the actual response value (str / response object / Exception).
        if callable(value) and not isinstance(value, type):
            value = value()
        if isinstance(value, BaseException):
            raise value
        if value is None:
            raise AssertionError("LLM chat called but no response configured")
        if hasattr(value, "choices"):  # caller supplied a ready response object
            return value
        return _chat_response(value)

    async def _transcribe(self, **kwargs: Any) -> Any:
        self.transcribe_calls.append(kwargs)
        value = self.transcription
        if callable(value) and not isinstance(value, type):
            value = value()
        if isinstance(value, BaseException):
            raise value
        if value is None:
            raise AssertionError("transcription called but no response configured")
        return value


class _FakeCompletions:
    def __init__(self, ctrl: LLMController) -> None:
        self._ctrl = ctrl

    async def create(self, **kwargs: Any) -> Any:
        return await self._ctrl._chat(**kwargs)


class _FakeTranscriptions:
    def __init__(self, ctrl: LLMController) -> None:
        self._ctrl = ctrl

    async def create(self, **kwargs: Any) -> Any:
        return await self._ctrl._transcribe(**kwargs)


class FakeOpenAI:
    def __init__(self, ctrl: LLMController) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(ctrl))
        self.audio = SimpleNamespace(transcriptions=_FakeTranscriptions(ctrl))


@pytest.fixture(autouse=True)
def llm(monkeypatch: pytest.MonkeyPatch) -> LLMController:
    """Patch every ``get_openai_client`` callsite to a configurable fake."""
    ctrl = LLMController()
    fake = FakeOpenAI(ctrl)
    monkeypatch.setattr("app.services.analysis.get_openai_client", lambda: fake)
    monkeypatch.setattr("app.llm.transcription.get_openai_client", lambda: fake)
    return ctrl


# ---------------------------------------------------------------------------
# Deterministic clock for streak / history (mocks the time used at finish)
# ---------------------------------------------------------------------------
class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now

    def set(self, value: datetime) -> None:
        self.now = value


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    c = Clock()
    monkeypatch.setattr("app.services.entry.utcnow", c)
    return c


# ---------------------------------------------------------------------------
# HTTP clients (ASGITransport against the real app)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def clients() -> AsyncIterator[Callable[..., Any]]:
    """Factory yielding device-scoped AsyncClients (auto-closed)."""
    created: list[httpx.AsyncClient] = []

    def factory(device_id: str | None = None) -> httpx.AsyncClient:
        did = str(device_id or uuid.uuid4())
        c = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Device-Id": did, "X-API-Key": TEST_API_KEY},
        )
        c.device_id = did  # type: ignore[attr-defined]
        created.append(c)
        return c

    yield factory
    for c in created:
        await c.aclose()


@pytest_asyncio.fixture
async def client(clients: Callable[..., httpx.AsyncClient]) -> httpx.AsyncClient:
    """A single default device-scoped client."""
    return clients()
