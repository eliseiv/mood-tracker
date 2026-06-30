"""Seed predefined catalog (levels, emotions, activities).

Revision ID: 0002_seed_catalog
Revises: 0001_initial
Create Date: 2026-06-26

Historical snapshot of the initial catalog. The data is INLINED here (frozen)
rather than imported from app.seed.catalog_seed: the live seed module evolves
(localization + 100 emotions, ADR-010 / migration 0005), and a historical
migration must stay reproducible regardless of later code changes. Migration
0005 transforms this baseline (rename label->label_en/label_ru, deactivate these
emotions, insert the new localized 100).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# Frozen baseline catalog (do not change — historical migration snapshot).
_MOOD_LEVELS = [
    {"value": 1, "code": "terrible", "label": "Terrible", "order": 1},
    {"value": 2, "code": "bad", "label": "Bad", "order": 2},
    {"value": 3, "code": "okay", "label": "Okay", "order": 3},
    {"value": 4, "code": "good", "label": "Good", "order": 4},
    {"value": 5, "code": "great", "label": "Great", "order": 5},
]

_EMOTIONS = [
    {"code": "anxious", "label": "Anxious", "level_value": 1, "order": 1},
    {"code": "angry", "label": "Angry", "level_value": 1, "order": 2},
    {"code": "hopeless", "label": "Hopeless", "level_value": 1, "order": 3},
    {"code": "overwhelmed", "label": "Overwhelmed", "level_value": 1, "order": 4},
    {"code": "devastated", "label": "Devastated", "level_value": 1, "order": 5},
    {"code": "sad", "label": "Sad", "level_value": 2, "order": 1},
    {"code": "tired", "label": "Tired", "level_value": 2, "order": 2},
    {"code": "stressed", "label": "Stressed", "level_value": 2, "order": 3},
    {"code": "frustrated", "label": "Frustrated", "level_value": 2, "order": 4},
    {"code": "lonely", "label": "Lonely", "level_value": 2, "order": 5},
    {"code": "neutral", "label": "Neutral", "level_value": 3, "order": 1},
    {"code": "calm", "label": "Calm", "level_value": 3, "order": 2},
    {"code": "bored", "label": "Bored", "level_value": 3, "order": 3},
    {"code": "unsure", "label": "Unsure", "level_value": 3, "order": 4},
    {"code": "content", "label": "Content", "level_value": 3, "order": 5},
    {"code": "happy", "label": "Happy", "level_value": 4, "order": 1},
    {"code": "relaxed", "label": "Relaxed", "level_value": 4, "order": 2},
    {"code": "motivated", "label": "Motivated", "level_value": 4, "order": 3},
    {"code": "hopeful", "label": "Hopeful", "level_value": 4, "order": 4},
    {"code": "grateful", "label": "Grateful", "level_value": 4, "order": 5},
    {"code": "joyful", "label": "Joyful", "level_value": 5, "order": 1},
    {"code": "excited", "label": "Excited", "level_value": 5, "order": 2},
    {"code": "energetic", "label": "Energetic", "level_value": 5, "order": 3},
    {"code": "proud", "label": "Proud", "level_value": 5, "order": 4},
    {"code": "loved", "label": "Loved", "level_value": 5, "order": 5},
]

_ACTIVITIES = [
    {"code": "work", "label": "Work"},
    {"code": "study", "label": "Study"},
    {"code": "sport", "label": "Sport"},
    {"code": "yoga", "label": "Yoga"},
    {"code": "reading", "label": "Reading"},
    {"code": "friends", "label": "Friends"},
    {"code": "family", "label": "Family"},
    {"code": "music", "label": "Music"},
    {"code": "cooking", "label": "Cooking"},
    {"code": "walking", "label": "Walking"},
    {"code": "meditation", "label": "Meditation"},
    {"code": "gaming", "label": "Gaming"},
    {"code": "travel", "label": "Travel"},
    {"code": "nature", "label": "Nature"},
    {"code": "sleep", "label": "Sleep"},
]

revision: str = "0002_seed_catalog"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_levels_table = sa.table(
    "mood_scale_levels",
    sa.column("id", sa.Uuid()),
    sa.column("value", sa.Integer()),
    sa.column("code", sa.String()),
    sa.column("label", sa.String()),
    sa.column("order", sa.Integer()),
)

_emotions_table = sa.table(
    "emotions",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.String()),
    sa.column("label", sa.String()),
    sa.column("scale_level_id", sa.Uuid()),
    sa.column("order", sa.Integer()),
    sa.column("is_active", sa.Boolean()),
)

_activities_table = sa.table(
    "activities",
    sa.column("id", sa.Uuid()),
    sa.column("label", sa.String()),
    sa.column("code", sa.String()),
    sa.column("device_id", sa.Uuid()),
    sa.column("is_custom", sa.Boolean()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    level_ids: dict[int, uuid.UUID] = {level["value"]: uuid.uuid4() for level in _MOOD_LEVELS}

    op.bulk_insert(
        _levels_table,
        [
            {
                "id": level_ids[level["value"]],
                "value": level["value"],
                "code": level["code"],
                "label": level["label"],
                "order": level["order"],
            }
            for level in _MOOD_LEVELS
        ],
    )

    op.bulk_insert(
        _emotions_table,
        [
            {
                "id": uuid.uuid4(),
                "code": emotion["code"],
                "label": emotion["label"],
                "scale_level_id": level_ids[emotion["level_value"]],
                "order": emotion["order"],
                "is_active": True,
            }
            for emotion in _EMOTIONS
        ],
    )

    now = datetime.now(UTC)
    op.bulk_insert(
        _activities_table,
        [
            {
                "id": uuid.uuid4(),
                "label": activity["label"],
                "code": activity["code"],
                "device_id": None,
                "is_custom": False,
                "created_at": now,
            }
            for activity in _ACTIVITIES
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM emotions")
    op.execute("DELETE FROM activities WHERE device_id IS NULL")
    op.execute("DELETE FROM mood_scale_levels")
