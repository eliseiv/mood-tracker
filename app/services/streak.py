"""Streak service: streak by local date with device timezone (Q-GAME-2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.logging import get_logger
from app.db.models import Device

logger = get_logger(__name__)


def set_device_timezone(device: Device, timezone: str | None) -> None:
    """Upsert a valid IANA timezone onto the device (last-write-wins).

    Invalid/unknown zones are ignored (logged) and never overwrite a stored
    value; no validation error is raised (Q-GAME-2, docs/04-api-contract §2).
    """
    if not timezone:
        return
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("invalid_timezone_ignored", timezone=timezone)
        return
    device.timezone = timezone


def local_date(now_utc: datetime, timezone: str | None) -> date:
    """Return the local calendar date for ``now_utc`` in the device timezone.

    Falls back to UTC when the timezone is missing or unknown.
    """
    if timezone:
        try:
            return now_utc.astimezone(ZoneInfo(timezone)).date()
        except (ZoneInfoNotFoundError, ValueError):
            logger.warning("invalid_timezone", timezone=timezone)
    return now_utc.date()


def update_streak(device: Device, today: date) -> None:
    """Update streak fields on the device for a finished entry on ``today``.

    - same day as last entry -> unchanged.
    - exactly the next day    -> current_streak += 1.
    - gap or first entry      -> current_streak = 1.
    """
    last = device.last_entry_date
    if last == today:
        return
    if last is not None and last == today - timedelta(days=1):
        device.current_streak += 1
    else:
        device.current_streak = 1
    device.longest_streak = max(device.longest_streak, device.current_streak)
    device.last_entry_date = today
