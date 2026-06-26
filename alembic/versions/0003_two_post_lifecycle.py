"""2-POST lifecycle: mood_scale_level_id NOT NULL.

Revision ID: 0003_two_post_lifecycle
Revises: 0002_seed_catalog
Create Date: 2026-06-26

Entry status enum is reduced to {awaiting_answer, finished} at the application
level (ADR-003). The status column is a plain VARCHAR (no DB CHECK constraint),
so no DDL change is needed for it. ``mood`` is now mandatory in POST /entries,
so ``mood_scale_level_id`` becomes NOT NULL.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_two_post_lifecycle"
down_revision: str | None = "0002_seed_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("mood_entries") as batch_op:
        batch_op.alter_column(
            "mood_scale_level_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("mood_entries") as batch_op:
        batch_op.alter_column(
            "mood_scale_level_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )
