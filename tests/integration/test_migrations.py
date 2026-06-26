"""Alembic migration 0003: mood_scale_level_id NOT NULL, reversible."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _alembic(db_path: Path, *args: str) -> None:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_path.as_posix()}",
        "OPENAI_API_KEY": "",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
    )


def _mood_level_notnull(db_path: Path) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        cols = conn.execute("PRAGMA table_info(mood_entries)").fetchall()
    finally:
        conn.close()
    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    row = next(c for c in cols if c[1] == "mood_scale_level_id")
    return bool(row[3])


def test_migration_0003_upgrade_and_downgrade_reversible(tmp_path: Path) -> None:
    db = tmp_path / f"mig_{uuid.uuid4().hex}.db"

    # upgrade head -> mood_scale_level_id NOT NULL
    _alembic(db, "upgrade", "head")
    assert _mood_level_notnull(db) is True

    # downgrade one step (0003 -> 0002) -> nullable again
    _alembic(db, "downgrade", "0002_seed_catalog")
    assert _mood_level_notnull(db) is False

    # upgrade back to head -> NOT NULL restored (fully reversible)
    _alembic(db, "upgrade", "head")
    assert _mood_level_notnull(db) is True
