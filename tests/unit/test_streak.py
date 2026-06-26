"""Unit tests for the streak service (local date + timezone, Q-GAME-2)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.db.models import Device
from app.services.streak import local_date, set_device_timezone, update_streak


def _device(**kwargs: object) -> Device:
    d = Device(id=None)
    d.current_streak = 0
    d.longest_streak = 0
    d.last_entry_date = None
    d.timezone = None
    for key, value in kwargs.items():
        setattr(d, key, value)
    return d


def test_local_date_uses_timezone_near_midnight_utc() -> None:
    # 2026-06-26 15:30 UTC -> Tokyo (UTC+9) is already 2026-06-27.
    now = datetime(2026, 6, 26, 15, 30, tzinfo=UTC)
    assert local_date(now, "Asia/Tokyo") == date(2026, 6, 27)
    assert local_date(now, None) == date(2026, 6, 26)


def test_local_date_invalid_timezone_falls_back_to_utc() -> None:
    now = datetime(2026, 6, 26, 15, 30, tzinfo=UTC)
    assert local_date(now, "Not/AZone") == date(2026, 6, 26)


def test_set_device_timezone_valid_upsert() -> None:
    device = _device()
    set_device_timezone(device, "Europe/Amsterdam")
    assert device.timezone == "Europe/Amsterdam"


def test_set_device_timezone_invalid_is_ignored() -> None:
    device = _device(timezone="Europe/Amsterdam")
    set_device_timezone(device, "Mars/Phobos")
    assert device.timezone == "Europe/Amsterdam"  # not overwritten with garbage


def test_set_device_timezone_none_is_noop() -> None:
    device = _device(timezone="Europe/Amsterdam")
    set_device_timezone(device, None)
    assert device.timezone == "Europe/Amsterdam"


def test_update_streak_first_entry() -> None:
    device = _device()
    update_streak(device, date(2026, 6, 26))
    assert device.current_streak == 1
    assert device.longest_streak == 1
    assert device.last_entry_date == date(2026, 6, 26)


def test_update_streak_consecutive_day_increments() -> None:
    device = _device(current_streak=3, longest_streak=3, last_entry_date=date(2026, 6, 25))
    update_streak(device, date(2026, 6, 26))
    assert device.current_streak == 4
    assert device.longest_streak == 4


def test_update_streak_gap_resets_but_keeps_longest() -> None:
    device = _device(current_streak=5, longest_streak=5, last_entry_date=date(2026, 6, 20))
    update_streak(device, date(2026, 6, 26))
    assert device.current_streak == 1
    assert device.longest_streak == 5


def test_update_streak_same_day_is_noop() -> None:
    device = _device(current_streak=2, longest_streak=4, last_entry_date=date(2026, 6, 26))
    update_streak(device, date(2026, 6, 26))
    assert device.current_streak == 2
    assert device.longest_streak == 4
