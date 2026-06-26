"""Points service: idempotent award via append-only ledger + denormalized balance."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, PointsLedger
from app.db.models.enums import PointsReason


async def award_entry_points(
    session: AsyncSession,
    device: Device,
    entry_id: uuid.UUID,
    points: int,
) -> int:
    """Award points for a finished entry, idempotently.

    A ledger row for ``(entry_id, entry_finished)`` is created at most once.
    The denormalized ``Device.points_balance`` is bumped with a SQL-level atomic
    increment (``UPDATE ... SET points_balance = points_balance + :delta``) rather
    than a Python read-modify-write, so two finishes of *different* entries on the
    same device cannot lose an update (the row lock in finish covers mood_entries,
    not devices). Runs in the same transaction as the ledger insert / analysis /
    streak; the idempotency guard ensures the increment happens at most once.
    Returns the number of points actually awarded (0 if already awarded).
    """
    existing = await session.scalar(
        select(PointsLedger).where(
            PointsLedger.entry_id == entry_id,
            PointsLedger.reason == PointsReason.ENTRY_FINISHED,
        )
    )
    if existing is not None:
        return 0
    session.add(
        PointsLedger(
            device_id=device.id,
            delta=points,
            reason=PointsReason.ENTRY_FINISHED,
            entry_id=entry_id,
        )
    )
    await session.execute(
        update(Device)
        .where(Device.id == device.id)
        .values(points_balance=Device.points_balance + points)
    )
    return points
