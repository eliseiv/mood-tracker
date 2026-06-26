"""device-id: UUID -> opaque String(64) (ADR-007, iteration 8).

Revision ID: 0004_device_id_string
Revises: 0003_two_post_lifecycle
Create Date: 2026-06-26

Changes Device.id (PK) and every referencing FK column
(mood_entries.device_id, activities.device_id, points_ledger.device_id) from
UUID to VARCHAR(64). Existing UUID values are preserved (``uuid::text`` keeps
``'f47ac10b-...'`` verbatim).

PostgreSQL: drop the three FK constraints (cannot change a referenced column's
type under an active FK), ALTER each column TYPE varchar(64) USING ...::text,
then re-add the FKs with ON DELETE CASCADE. Indexes / PK / unique constraints
are rebuilt automatically by PostgreSQL on the type change.

SQLite (local/CI): identifiers have TEXT affinity regardless of the declared
type, so the change is a no-op for stored data and FK matching (by value) keeps
working. ``batch_alter_table`` re-declares only ``devices.id`` (PK, no expression
indexes) for schema consistency; the child FK columns are left as-is on SQLite —
re-declaring them would require recreating the partial/expression indexes on
``points_ledger``, ``activities`` and ``mood_entries``, which SQLite batch mode
cannot reflect reliably, for no behavioural benefit.

DOWNGRADE is reversible (varchar -> uuid USING ...::uuid) ONLY while every
device id is a valid UUID. Once any non-UUID id exists (e.g. ``testuser``) the
downgrade fails — an intentional one-way consequence (ADR-007).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_device_id_string"
down_revision: str | None = "0003_two_post_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, fk column, nullable) for the referencing FK columns.
_FK_COLUMNS = [
    ("mood_entries", "device_id", False),
    ("activities", "device_id", True),
    ("points_ledger", "device_id", False),
]
_FK_NAMES = {
    "mood_entries": "mood_entries_device_id_fkey",
    "activities": "activities_device_id_fkey",
    "points_ledger": "points_ledger_device_id_fkey",
}


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect == "postgresql":
        for table in _FK_NAMES:
            op.drop_constraint(_FK_NAMES[table], table, type_="foreignkey")
        op.alter_column(
            "devices",
            "id",
            existing_type=sa.Uuid(),
            type_=sa.String(length=64),
            existing_nullable=False,
            postgresql_using="id::text",
        )
        for table, column, nullable in _FK_COLUMNS:
            op.alter_column(
                table,
                column,
                existing_type=sa.Uuid(),
                type_=sa.String(length=64),
                existing_nullable=nullable,
                postgresql_using=f"{column}::text",
            )
        for table, column, _ in _FK_COLUMNS:
            op.create_foreign_key(
                _FK_NAMES[table], table, "devices", [column], ["id"], ondelete="CASCADE"
            )
        return

    # SQLite (and any other backend): TEXT affinity -> data no-op. Re-declare only
    # the PK type; child FK columns keep working by value (see module docstring).
    with op.batch_alter_table("devices") as batch_op:
        batch_op.alter_column(
            "id", existing_type=sa.Uuid(), type_=sa.String(length=64), existing_nullable=False
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect == "postgresql":
        for table in _FK_NAMES:
            op.drop_constraint(_FK_NAMES[table], table, type_="foreignkey")
        for table, column, nullable in _FK_COLUMNS:
            op.alter_column(
                table,
                column,
                existing_type=sa.String(length=64),
                type_=sa.Uuid(),
                existing_nullable=nullable,
                postgresql_using=f"{column}::uuid",
            )
        op.alter_column(
            "devices",
            "id",
            existing_type=sa.String(length=64),
            type_=sa.Uuid(),
            existing_nullable=False,
            postgresql_using="id::uuid",
        )
        for table, column, _ in _FK_COLUMNS:
            op.create_foreign_key(
                _FK_NAMES[table], table, "devices", [column], ["id"], ondelete="CASCADE"
            )
        return

    with op.batch_alter_table("devices") as batch_op:
        batch_op.alter_column(
            "id", existing_type=sa.String(length=64), type_=sa.Uuid(), existing_nullable=False
        )
