"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.types.TypeEngine[object]:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=35), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("points_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_entry_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mood_scale_levels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("value"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "emotions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("scale_level_id", sa.Uuid(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["scale_level_id"], ["mood_scale_levels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_emotions_scale_level_id", "emotions", ["scale_level_id"])

    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activities_device_id", "activities", ["device_id"])
    # Custom activities dedup: unique (device_id, lower(label)).
    op.create_index(
        "uq_activity_custom_label",
        "activities",
        ["device_id", sa.text("lower(label)")],
        unique=True,
    )
    # Global predefined activities dedup: unique lower(label) where device_id IS NULL.
    op.create_index(
        "uq_activity_global_label",
        "activities",
        [sa.text("lower(label)")],
        unique=True,
        sqlite_where=sa.text("device_id IS NULL"),
        postgresql_where=sa.text("device_id IS NULL"),
    )

    op.create_table(
        "mood_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("mood_scale_level_id", sa.Uuid(), nullable=True),
        sa.Column("language", sa.String(length=35), nullable=True),
        sa.Column("points_awarded", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mood_scale_level_id"], ["mood_scale_levels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mood_entries_device_status", "mood_entries", ["device_id", "status"])
    op.create_index(
        "ix_mood_entries_device_finished",
        "mood_entries",
        ["device_id", sa.text("finished_at DESC")],
    )

    op.create_table(
        "entry_emotions",
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("emotion_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["mood_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["emotion_id"], ["emotions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entry_id", "emotion_id"),
    )

    op.create_table(
        "entry_activities",
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["mood_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entry_id", "activity_id"),
    )

    op.create_table(
        "entry_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=True),
        sa.Column("prompt_version", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["mood_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entry_messages_entry_id", "entry_messages", ["entry_id"])

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("overview", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=35), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=16), nullable=False),
        sa.Column("raw_response", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["mood_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_id"),
    )

    op.create_table(
        "advice_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analysis_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_advice_sections_analysis_id", "advice_sections", ["analysis_id"])

    op.create_table(
        "points_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entry_id"], ["mood_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_points_ledger_device_id", "points_ledger", ["device_id"])
    op.create_index(
        "uq_points_ledger_entry_reason",
        "points_ledger",
        ["entry_id", "reason"],
        unique=True,
        sqlite_where=sa.text("entry_id IS NOT NULL"),
        postgresql_where=sa.text("entry_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("points_ledger")
    op.drop_table("advice_sections")
    op.drop_table("analysis_results")
    op.drop_table("entry_messages")
    op.drop_table("entry_activities")
    op.drop_table("entry_emotions")
    op.drop_table("mood_entries")
    op.drop_table("activities")
    op.drop_table("emotions")
    op.drop_table("mood_scale_levels")
    op.drop_table("devices")
