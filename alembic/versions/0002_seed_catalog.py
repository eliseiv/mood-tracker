"""Seed predefined catalog (levels, emotions, activities).

Revision ID: 0002_seed_catalog
Revises: 0001_initial
Create Date: 2026-06-26

Values come from app.seed.catalog_seed (single source of truth). The exact
content is pending Q-CATALOG-1 (Figma); structure is final.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.seed.catalog_seed import ACTIVITIES, EMOTIONS, MOOD_LEVELS

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
    level_ids: dict[int, uuid.UUID] = {level["value"]: uuid.uuid4() for level in MOOD_LEVELS}

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
            for level in MOOD_LEVELS
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
            for emotion in EMOTIONS
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
            for activity in ACTIVITIES
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM emotions")
    op.execute("DELETE FROM activities WHERE device_id IS NULL")
    op.execute("DELETE FROM mood_scale_levels")
