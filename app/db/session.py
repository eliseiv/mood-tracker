"""Async engine / session management and the FastAPI DB dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _enable_sqlite_fk(engine: AsyncEngine) -> None:
    """Enforce foreign keys on SQLite (needed for cascade deletes)."""

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragma(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_engine() -> AsyncEngine:
    """Return the lazily-created async engine singleton."""
    global _engine
    if _engine is None:
        settings = get_settings()
        is_sqlite = settings.database_url.startswith("sqlite")
        # pool_pre_ping guards against stale server connections (Postgres);
        # it is unnecessary for SQLite and incompatible with aiosqlite checkout.
        _engine = create_async_engine(
            settings.database_url,
            future=True,
            pool_pre_ping=not is_sqlite,
        )
        if _engine.dialect.name == "sqlite":
            _enable_sqlite_fk(_engine)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the lazily-created session factory singleton."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped async session."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session
