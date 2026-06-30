"""Alembic migrations: 0003 (NOT NULL) and 0004 (device-id UUID -> String(64)).

SQLite runs in-process for every test. The Postgres run (prod-parity for the
0004 type change on a referenced PK) is executed only when MT_TEST_POSTGRES_URL
points at a reachable Postgres; otherwise it is skipped with a clear marker.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PG_URL = os.environ.get("MT_TEST_POSTGRES_URL")  # postgresql+asyncpg://...


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------
def _alembic(db_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_path.as_posix()}",
        "OPENAI_API_KEY": "",
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_PROJECT_ROOT,
        env=env,
        check=check,
        capture_output=True,
    )


def _column(db_path: Path, table: str, column: str) -> tuple[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    finally:
        conn.close()
    row = next(c for c in cols if c[1] == column)
    return row[2], row[3]  # (declared type, notnull)


def _alembic_version(db_path: Path) -> str:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 0003 — mood_scale_level_id NOT NULL, reversible
# ---------------------------------------------------------------------------
def test_migration_0003_upgrade_and_downgrade_reversible(tmp_path: Path) -> None:
    db = tmp_path / f"mig_{uuid.uuid4().hex}.db"
    _alembic(db, "upgrade", "0003_two_post_lifecycle")
    assert _column(db, "mood_entries", "mood_scale_level_id")[1] == 1  # NOT NULL
    _alembic(db, "downgrade", "0002_seed_catalog")
    assert _column(db, "mood_entries", "mood_scale_level_id")[1] == 0  # nullable
    _alembic(db, "upgrade", "0003_two_post_lifecycle")
    assert _column(db, "mood_entries", "mood_scale_level_id")[1] == 1


# ---------------------------------------------------------------------------
# 0004 — device-id UUID -> String(64) on SQLite
# ---------------------------------------------------------------------------
def test_upgrade_head_has_string_device_id_and_reaches_0005(tmp_path: Path) -> None:
    db = tmp_path / f"mig_{uuid.uuid4().hex}.db"
    _alembic(db, "upgrade", "head")
    assert _alembic_version(db) == "0005_catalog_localization"
    decl_type, _ = _column(db, "devices", "id")  # 0004 type change persists
    assert "VARCHAR(64)" in decl_type.upper() or "CHAR(64)" in decl_type.upper()


def test_0004_preserves_existing_rows_and_cascade_sqlite(tmp_path: Path) -> None:
    db = tmp_path / f"mig_{uuid.uuid4().hex}.db"
    # Create rows on the 0003 (UUID) schema, then migrate to 0004.
    _alembic(db, "upgrade", "0003_two_post_lifecycle")
    dev = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    now = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "INSERT INTO devices (id, points_balance, current_streak, longest_streak,"
            " created_at, last_seen_at) VALUES (?, 20, 1, 1, ?, ?)",
            (dev, now, now),
        )
        conn.execute(
            "INSERT INTO points_ledger (id, device_id, delta, reason, created_at)"
            " VALUES (?, ?, 20, 'entry_finished', ?)",
            (uuid.uuid4().hex, dev, now),
        )
        conn.commit()
    finally:
        conn.close()

    _alembic(db, "upgrade", "head")  # 0003 -> 0004

    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        # Rows preserved verbatim across the migration.
        assert conn.execute("SELECT id FROM devices").fetchone()[0] == dev
        assert conn.execute("SELECT device_id FROM points_ledger").fetchone()[0] == dev
        # ON DELETE CASCADE: deleting the device removes the ledger row.
        conn.execute("DELETE FROM devices WHERE id = ?", (dev,))
        conn.commit()
        assert conn.execute("SELECT count(*) FROM points_ledger").fetchone()[0] == 0
    finally:
        conn.close()


def test_downgrade_0004_to_0003_sqlite(tmp_path: Path) -> None:
    db = tmp_path / f"mig_{uuid.uuid4().hex}.db"
    _alembic(db, "upgrade", "0004_device_id_string")
    _alembic(db, "downgrade", "0003_two_post_lifecycle")
    assert _alembic_version(db) == "0003_two_post_lifecycle"
    _alembic(db, "upgrade", "0004_device_id_string")
    assert _alembic_version(db) == "0004_device_id_string"


# ---------------------------------------------------------------------------
# 0005 — catalog localization (EN/RU, 100 emotions) on SQLite
# ---------------------------------------------------------------------------
def _active_emotion_count(db: Path) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT count(*) FROM emotions WHERE is_active=1").fetchone()[0]
    finally:
        conn.close()


def test_0005_non_destructive_preserves_legacy_link_sqlite(tmp_path: Path) -> None:
    db = tmp_path / f"mig_{uuid.uuid4().hex}.db"
    # Build the legacy (0004) catalog and an entry linked to a legacy emotion.
    _alembic(db, "upgrade", "0004_device_id_string")
    dev = "legacy-device"
    entry_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        level1 = conn.execute("SELECT id FROM mood_scale_levels WHERE value=1").fetchone()[0]
        anxious_id = conn.execute("SELECT id FROM emotions WHERE code='anxious'").fetchone()[0]
        conn.execute(
            "INSERT INTO devices (id, points_balance, current_streak, longest_streak,"
            " created_at, last_seen_at) VALUES (?, 0, 0, 0, ?, ?)",
            (dev, now, now),
        )
        conn.execute(
            "INSERT INTO mood_entries (id, device_id, status, mood_scale_level_id, created_at)"
            " VALUES (?, ?, 'awaiting_answer', ?, ?)",
            (entry_id, dev, level1, now),
        )
        conn.execute(
            "INSERT INTO entry_emotions (entry_id, emotion_id) VALUES (?, ?)",
            (entry_id, anxious_id),
        )
        conn.commit()
    finally:
        conn.close()

    _alembic(db, "upgrade", "head")  # 0004 -> 0005

    conn = sqlite3.connect(db)
    try:
        # Legacy emotion kept (not deleted), deactivated; link intact.
        anxious = conn.execute("SELECT is_active FROM emotions WHERE code='anxious'").fetchone()
        assert anxious is not None and anxious[0] == 0
        link = conn.execute(
            "SELECT count(*) FROM entry_emotions ee JOIN emotions e ON e.id=ee.emotion_id"
            " WHERE e.code='anxious' AND ee.entry_id=?",
            (entry_id,),
        ).fetchone()[0]
        assert link == 1
        # New localized catalog present.
        assert _active_emotion_count(db) == 100
        assert (
            conn.execute("SELECT code FROM mood_scale_levels WHERE value=3").fetchone()[0]
            == "neutral"
        )
        assert (
            conn.execute("SELECT code FROM mood_scale_levels WHERE value=5").fetchone()[0]
            == "awesome"
        )
        # label_en / label_ru NOT NULL for all rows.
        assert (
            conn.execute("SELECT count(*) FROM emotions WHERE label_ru IS NULL").fetchone()[0] == 0
        )
        assert (
            conn.execute("SELECT count(*) FROM emotions WHERE label_en IS NULL").fetchone()[0] == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM mood_scale_levels WHERE label_ru IS NULL"
            ).fetchone()[0]
            == 0
        )
    finally:
        conn.close()


def test_0005_downgrade_reactivates_legacy_and_removes_new_sqlite(tmp_path: Path) -> None:
    db = tmp_path / f"mig_{uuid.uuid4().hex}.db"
    _alembic(db, "upgrade", "head")
    assert _active_emotion_count(db) == 100
    _alembic(db, "downgrade", "0004_device_id_string")
    assert _alembic_version(db) == "0004_device_id_string"
    conn = sqlite3.connect(db)
    try:
        # New emotions removed, legacy reactivated, level codes reverted.
        assert (
            conn.execute(
                "SELECT count(*) FROM emotions WHERE code='terrible_devastated'"
            ).fetchone()[0]
            == 0
        )
        assert conn.execute("SELECT count(*) FROM emotions WHERE is_active=1").fetchone()[0] == 25
        assert (
            conn.execute("SELECT code FROM mood_scale_levels WHERE value=3").fetchone()[0] == "okay"
        )
        assert (
            conn.execute("SELECT code FROM mood_scale_levels WHERE value=5").fetchone()[0]
            == "great"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Postgres prod-parity runs (skipped unless a Postgres is reachable)
# ---------------------------------------------------------------------------
def _pg_dsn() -> str:
    assert _PG_URL is not None
    return _PG_URL.replace("+asyncpg", "")


def _alembic_pg(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    env = {**os.environ, "DATABASE_URL": _PG_URL or "", "OPENAI_API_KEY": ""}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_PROJECT_ROOT,
        env=env,
        check=check,
        capture_output=True,
    )


@pytest.mark.skipif(not _PG_URL, reason="MT_TEST_POSTGRES_URL not set — Postgres run skipped")
@pytest.mark.asyncio
async def test_0004_postgres_type_change_preserves_data_and_fks() -> None:
    import asyncpg

    dsn = _pg_dsn()
    dev = "f47ac10b-58cc-4372-a567-0e02b2c3d479"

    # Clean schema for a deterministic run.
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()

    # Build the UUID-typed schema (0003) and seed a UUID device + children.
    _alembic_pg("upgrade", "0003_two_post_lifecycle")
    conn = await asyncpg.connect(dsn)
    try:
        level_id = await conn.fetchval("SELECT id FROM mood_scale_levels WHERE value = 2")
        entry_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO devices (id, points_balance, current_streak, longest_streak,"
            " created_at, last_seen_at) VALUES ($1, 20, 1, 1, now(), now())",
            uuid.UUID(dev),
        )
        await conn.execute(
            "INSERT INTO mood_entries (id, device_id, status, mood_scale_level_id, created_at)"
            " VALUES ($1, $2, 'finished', $3, now())",
            entry_id,
            uuid.UUID(dev),
            level_id,
        )
        await conn.execute(
            "INSERT INTO points_ledger (id, device_id, delta, reason, entry_id, created_at)"
            " VALUES ($1, $2, 20, 'entry_finished', $3, now())",
            uuid.uuid4(),
            uuid.UUID(dev),
            entry_id,
        )
    finally:
        await conn.close()

    # The type-changing migration on a referenced PK + its FKs.
    _alembic_pg("upgrade", "head")

    conn = await asyncpg.connect(dsn)
    try:
        # 1) device-id columns became varchar(64); entry id stays uuid.
        types = {
            (r["table_name"], r["column_name"]): (r["data_type"], r["character_maximum_length"])
            for r in await conn.fetch(
                "SELECT table_name, column_name, data_type, character_maximum_length"
                " FROM information_schema.columns WHERE column_name IN ('id','device_id')"
                " AND table_name IN ('devices','mood_entries','activities','points_ledger')"
            )
        }
        assert types[("devices", "id")] == ("character varying", 64)
        assert types[("mood_entries", "device_id")] == ("character varying", 64)
        assert types[("activities", "device_id")] == ("character varying", 64)
        assert types[("points_ledger", "device_id")] == ("character varying", 64)
        assert types[("mood_entries", "id")][0] == "uuid"  # entry id unchanged

        # 2) UUID values preserved verbatim (as text).
        assert await conn.fetchval("SELECT id FROM devices") == dev
        assert await conn.fetchval("SELECT device_id FROM points_ledger") == dev

        # 3) FK ON DELETE CASCADE intact on all three child tables.
        deltypes = {
            r["conname"]: r["confdeltype"]
            for r in await conn.fetch(
                "SELECT conname, confdeltype::text FROM pg_constraint"
                " WHERE contype='f' AND confrelid='devices'::regclass"
            )
        }
        assert set(deltypes.values()) == {"c"}  # all CASCADE
        assert len(deltypes) == 3

        # 4) Partial / functional / DESC indexes intact.
        idx = {
            r["indexname"]
            for r in await conn.fetch(
                "SELECT indexname FROM pg_indexes WHERE indexname = ANY($1::text[])",
                [
                    "uq_activity_custom_label",
                    "uq_activity_global_label",
                    "uq_points_ledger_entry_reason",
                    "ix_mood_entries_device_finished",
                ],
            )
        }
        assert idx == {
            "uq_activity_custom_label",
            "uq_activity_global_label",
            "uq_points_ledger_entry_reason",
            "ix_mood_entries_device_finished",
        }

        # 5) CASCADE delete removes children.
        await conn.execute("DELETE FROM devices WHERE id = $1", dev)
        assert await conn.fetchval("SELECT count(*) FROM mood_entries") == 0
        assert await conn.fetchval("SELECT count(*) FROM points_ledger") == 0
    finally:
        await conn.close()


@pytest.mark.skipif(not _PG_URL, reason="MT_TEST_POSTGRES_URL not set — Postgres run skipped")
@pytest.mark.asyncio
async def test_0004_postgres_downgrade_reversible_only_with_uuid_ids() -> None:
    import asyncpg

    dsn = _pg_dsn()
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()

    _alembic_pg("upgrade", "head")

    # Downgrade succeeds while every id is a valid UUID.
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            "INSERT INTO devices (id, points_balance, current_streak, longest_streak,"
            " created_at, last_seen_at) VALUES"
            " ('f47ac10b-58cc-4372-a567-0e02b2c3d479', 0, 0, 0, now(), now())"
        )
    finally:
        await conn.close()
    _alembic_pg("downgrade", "0003_two_post_lifecycle")
    conn = await asyncpg.connect(dsn)
    try:
        dtype = await conn.fetchval(
            "SELECT data_type FROM information_schema.columns"
            " WHERE table_name='devices' AND column_name='id'"
        )
        assert dtype == "uuid"
    finally:
        await conn.close()

    # Re-upgrade, insert a non-UUID id, and confirm the downgrade is blocked.
    _alembic_pg("upgrade", "head")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            "INSERT INTO devices (id, points_balance, current_streak, longest_streak,"
            " created_at, last_seen_at) VALUES ('testuser', 0, 0, 0, now(), now())"
        )
    finally:
        await conn.close()
    result = _alembic_pg("downgrade", "0003_two_post_lifecycle", check=False)
    assert result.returncode != 0  # cannot cast 'testuser' to uuid -> one-way

    conn = await asyncpg.connect(dsn)
    try:
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        # Alembic runs the whole downgrade in one transaction; the 0004->0003 cast
        # failure rolls back the entire chain, so the DB stays at head.
        assert version == "0005_catalog_localization"
    finally:
        await conn.close()


@pytest.mark.skipif(not _PG_URL, reason="MT_TEST_POSTGRES_URL not set — Postgres run skipped")
@pytest.mark.asyncio
async def test_0005_postgres_localization_non_destructive() -> None:
    import asyncpg

    dsn = _pg_dsn()
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()

    # Legacy (0004) catalog + an entry linked to a legacy emotion.
    _alembic_pg("upgrade", "0004_device_id_string")
    dev = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    entry_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn)
    try:
        level1 = await conn.fetchval("SELECT id FROM mood_scale_levels WHERE value=1")
        anxious_id = await conn.fetchval("SELECT id FROM emotions WHERE code='anxious'")
        assert await conn.fetchval("SELECT label FROM emotions WHERE code='anxious'") == "Anxious"
        await conn.execute(
            "INSERT INTO devices (id, points_balance, current_streak, longest_streak,"
            " created_at, last_seen_at) VALUES ($1, 0, 0, 0, now(), now())",
            dev,
        )
        await conn.execute(
            "INSERT INTO mood_entries (id, device_id, status, mood_scale_level_id, created_at)"
            " VALUES ($1, $2, 'awaiting_answer', $3, now())",
            entry_id,
            dev,
            level1,
        )
        await conn.execute(
            "INSERT INTO entry_emotions (entry_id, emotion_id) VALUES ($1, $2)",
            entry_id,
            anxious_id,
        )
    finally:
        await conn.close()

    _alembic_pg("upgrade", "head")  # 0004 -> 0005

    conn = await asyncpg.connect(dsn)
    try:
        # rename label -> label_en preserved EN; label_ru backfilled + NOT NULL.
        assert (
            await conn.fetchval("SELECT label_en FROM emotions WHERE code='anxious'") == "Anxious"
        )
        nullable = {
            (r["table_name"], r["column_name"]): r["is_nullable"]
            for r in await conn.fetch(
                "SELECT table_name, column_name, is_nullable FROM information_schema.columns"
                " WHERE column_name IN ('label_en','label_ru')"
                " AND table_name IN ('emotions','mood_scale_levels')"
            )
        }
        assert nullable[("emotions", "label_ru")] == "NO"
        assert nullable[("mood_scale_levels", "label_ru")] == "NO"

        # Legacy deactivated (not deleted); entry_emotions link intact.
        assert await conn.fetchval("SELECT is_active FROM emotions WHERE code='anxious'") is False
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM entry_emotions ee JOIN emotions e ON e.id=ee.emotion_id"
                " WHERE e.code='anxious' AND ee.entry_id=$1",
                entry_id,
            )
            == 1
        )

        # New localized catalog: 100 active; levels 3/5 = neutral/awesome.
        assert await conn.fetchval("SELECT count(*) FROM emotions WHERE is_active") == 100
        assert await conn.fetchval("SELECT code FROM mood_scale_levels WHERE value=3") == "neutral"
        assert await conn.fetchval("SELECT code FROM mood_scale_levels WHERE value=5") == "awesome"
        assert (
            await conn.fetchval("SELECT label_ru FROM emotions WHERE code='terrible_devastated'")
            == "Опустошённый"
        )

        # FK emotions -> mood_scale_levels (CASCADE) and its index still present.
        deltype = await conn.fetchval(
            "SELECT confdeltype::text FROM pg_constraint"
            " WHERE contype='f' AND conrelid='emotions'::regclass"
            " AND confrelid='mood_scale_levels'::regclass"
        )
        assert deltype == "c"
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM pg_indexes WHERE indexname='ix_emotions_scale_level_id'"
            )
            == 1
        )
    finally:
        await conn.close()
