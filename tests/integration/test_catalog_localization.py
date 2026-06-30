"""Localized EN/RU catalog (ADR-010): GET /moods, language resolution, 100 emotions."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from app.db.models import Emotion, MoodScaleLevel
from app.db.session import get_sessionmaker
from app.seed.catalog_seed import EMOTIONS, MOOD_LEVELS, seed_catalog
from tests.helpers import API, create_awaiting, finish

pytestmark = pytest.mark.asyncio

_LEVEL_CODES = ["terrible", "bad", "neutral", "good", "awesome"]
_TSV = Path(__file__).resolve().parents[2] / "docs" / "modules" / "catalog" / "emotion_catalog.tsv"


# --- GET /moods : EN (default) ---------------------------------------------
async def test_moods_default_en_structure_and_labels(client: Any) -> None:
    r = await client.get(f"{API}/moods")
    assert r.status_code == 200
    levels = r.json()["levels"]
    assert [lv["code"] for lv in levels] == _LEVEL_CODES
    assert [lv["value"] for lv in levels] == [1, 2, 3, 4, 5]
    # EN labels.
    assert levels[0]["label"] == "Terrible"
    assert levels[2]["label"] == "Neutral"
    assert levels[4]["label"] == "Awesome"
    # Exactly 100 active emotions, 20 per level.
    counts = [len(lv["emotions"]) for lv in levels]
    assert counts == [20, 20, 20, 20, 20]
    assert sum(counts) == 100
    # Emotion EN label + non-localized code (suggested_key).
    first = levels[0]["emotions"][0]
    assert first["code"] == "terrible_devastated"
    assert first["label"] == "Devastated"


async def test_moods_codes_are_suggested_keys_not_localized(client: Any) -> None:
    en = (await client.get(f"{API}/moods")).json()
    ru = (await client.get(f"{API}/moods?language=ru")).json()
    en_codes = [e["code"] for lv in en["levels"] for e in lv["emotions"]]
    ru_codes = [e["code"] for lv in ru["levels"] for e in lv["emotions"]]
    assert en_codes == ru_codes  # codes never localized
    assert all("_" in c for c in en_codes)  # all are <level>_<emotion> keys


# --- GET /moods?language=ru -------------------------------------------------
async def test_moods_ru_labels(client: Any) -> None:
    r = await client.get(f"{API}/moods?language=ru")
    levels = r.json()["levels"]
    assert levels[0]["label"] == "Ужасно"
    assert levels[2]["label"] == "Нейтрально"
    assert levels[4]["label"] == "Отлично"
    first = levels[0]["emotions"][0]
    assert first["code"] == "terrible_devastated"  # code unchanged
    assert first["label"] == "Опустошённый"


# --- Language resolution (ADR-010) -----------------------------------------
async def test_query_language_overrides_accept_language(client: Any) -> None:
    r = await client.get(f"{API}/moods?language=ru", headers={"Accept-Language": "en-US"})
    assert r.json()["levels"][0]["label"] == "Ужасно"


async def test_accept_language_ru_resolves_ru(client: Any) -> None:
    r = await client.get(f"{API}/moods", headers={"Accept-Language": "ru-RU,ru;q=0.9"})
    assert r.json()["levels"][0]["label"] == "Ужасно"


async def test_unknown_language_falls_back_to_en(client: Any) -> None:
    r = await client.get(f"{API}/moods?language=de")
    assert r.json()["levels"][0]["label"] == "Terrible"


async def test_no_language_defaults_to_en(client: Any) -> None:
    r = await client.get(f"{API}/moods")
    assert r.json()["levels"][0]["label"] == "Terrible"


async def test_ru_primary_subtag_resolves_ru(client: Any) -> None:
    r = await client.get(f"{API}/moods?language=ru-Cyrl-RU")
    assert r.json()["levels"][0]["label"] == "Ужасно"


# --- Only active emotions are exposed --------------------------------------
async def test_moods_excludes_legacy_inactive_emotions(client: Any) -> None:
    codes = {
        e["code"]
        for lv in (await client.get(f"{API}/moods")).json()["levels"]
        for e in lv["emotions"]
    }
    for legacy in ("anxious", "angry", "sad", "tired", "calm", "happy", "joyful"):
        assert legacy not in codes
    assert len(codes) == 100


# --- POST /entries with new keys -------------------------------------------
async def test_create_entry_with_new_emotion_key(client: Any, llm: Any) -> None:
    llm.set_followup("q?")
    r = await client.post(
        f"{API}/entries",
        json={"mood": 1, "emotions": ["terrible_devastated"], "description": "x"},
    )
    assert r.status_code == 201


async def test_create_entry_empty_emotions_valid(client: Any, llm: Any) -> None:
    llm.set_followup("q?")
    r = await client.post(f"{API}/entries", json={"mood": 1, "emotions": [], "description": "x"})
    assert r.status_code == 201


async def test_full_lifecycle_with_new_keys(client: Any, llm: Any) -> None:
    entry_id = await create_awaiting(
        client, llm, mood=1, emotions=["terrible_devastated", "terrible_panicked"]
    )
    r = await finish(client, llm, entry_id)
    assert r.status_code == 200
    assert r.json()["reward"]["points_awarded"] == 20


# --- Seed idempotency + label NOT NULL + TSV consistency (DB-level) --------
async def test_seed_idempotent_active_100_no_dupes() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await seed_catalog(session)  # re-run startup seed
    async with sessionmaker() as session:
        active = await session.scalar(
            select(func.count()).select_from(Emotion).where(Emotion.is_active.is_(True))
        )
        distinct_codes = await session.scalar(select(func.count(func.distinct(Emotion.code))))
        total = await session.scalar(select(func.count()).select_from(Emotion))
        legacy_active = await session.scalar(
            select(func.count())
            .select_from(Emotion)
            .where(Emotion.is_active.is_(True), Emotion.code == "anxious")
        )
    assert active == 100
    assert distinct_codes == total  # no duplicate codes
    assert legacy_active == 0  # legacy stays deactivated


async def test_all_labels_not_null_and_nonempty() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        levels = list((await session.scalars(select(MoodScaleLevel))).all())
        emotions = list((await session.scalars(select(Emotion))).all())
    assert len(levels) == 5
    for lv in levels:
        assert lv.label_en and lv.label_ru
    # All emotions (incl. deactivated legacy) have both labels (0005 backfill).
    for e in emotions:
        assert e.label_en and e.label_ru


def _read_tsv() -> list[dict[str, str]]:
    with _TSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


async def test_seed_migration_tsv_consistency() -> None:
    tsv = _read_tsv()
    assert len(tsv) == 100
    tsv_by_key = {row["suggested_key"]: row for row in tsv}

    # 1) seed EMOTIONS matches the TSV exactly (codes, labels, level, order).
    assert len(EMOTIONS) == 100
    assert {e["code"] for e in EMOTIONS} == set(tsv_by_key)
    for e in EMOTIONS:
        row = tsv_by_key[e["code"]]
        assert e["label_en"] == row["emotion_en"]
        assert e["label_ru"] == row["emotion_ru"]
        assert e["level_value"] == int(row["intensity_score"])
        assert e["order"] == int(row["order"])

    # 2) DB active emotions (post-migration) match the seed/TSV.
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        rows = list(
            (await session.scalars(select(Emotion).where(Emotion.is_active.is_(True)))).all()
        )
    db = {r.code: r for r in rows}
    assert set(db) == set(tsv_by_key)
    for code, row in tsv_by_key.items():
        assert db[code].label_en == row["emotion_en"]
        assert db[code].label_ru == row["emotion_ru"]

    # 3) Level codes consistent (seed <-> expected final set).
    assert [lv["code"] for lv in MOOD_LEVELS] == _LEVEL_CODES
