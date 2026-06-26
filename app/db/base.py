"""Declarative base and shared column types for cross-database support.

PK = UUID (native on PostgreSQL, CHAR(32) on SQLite). Timestamps are
timezone-aware UTC. JSONB on PostgreSQL degrades to JSON on SQLite.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeEngine


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def json_variant() -> TypeEngine[Any]:
    """JSONB on PostgreSQL, JSON on SQLite/other backends."""
    return JSONB().with_variant(JSON(), "sqlite")
