"""The app's only source of "now" (design.md §2).

Nothing else may call datetime.now(): every rule and timestamp goes through a Clock,
so tests and the rules report can pin time to APP_NOW.

The running clock is APP_NOW plus the real time elapsed since it first started. That start is
stored in the database (`app_clock`), so restarting the API resumes the same timeline instead
of jumping back to APP_NOW. The system clock is only used to measure elapsed time.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol

from sqlalchemy import Connection, text

from app.config import Settings, get_settings


class Clock(Protocol):
    def now(self) -> datetime: ...


def _as_utc(at: datetime) -> datetime:
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Clock needs a datetime with a time zone, got a naive one")
    return at.astimezone(UTC)


class FrozenClock:
    """Always returns the same instant. Tests move it explicitly."""

    def __init__(self, at: datetime) -> None:
        self._at = _as_utc(at)

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        self._at = _as_utc(at)

    def advance(self, delta: timedelta) -> None:
        self._at += delta


class RunningClock:
    """Starts at `anchor` and advances in real time from when it was created."""

    def __init__(self, anchor: datetime, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._anchor = _as_utc(anchor)
        self._monotonic = monotonic
        self._started = monotonic()

    def now(self) -> datetime:
        return self._anchor + timedelta(seconds=self._monotonic() - self._started)


def _wall_now() -> datetime:
    return datetime.now(UTC)


def clock_start(conn: Connection, app_now: datetime, wall_now: datetime) -> datetime:
    """Wall time at which the clock for `app_now` started; recorded on first use.

    A different APP_NOW starts a new clock. Safe under concurrent starts (single-row upsert).
    """
    row = conn.execute(
        text(
            "INSERT INTO app_clock (id, app_now, started_at) VALUES (1, :app_now, :wall) "
            "ON CONFLICT (id) DO UPDATE SET app_now = EXCLUDED.app_now, "
            "started_at = EXCLUDED.started_at WHERE app_clock.app_now <> EXCLUDED.app_now "
            "RETURNING started_at"
        ),
        {"app_now": app_now, "wall": wall_now},
    ).scalar()
    if row is None:  # unchanged APP_NOW: keep the stored start
        row = conn.execute(text("SELECT started_at FROM app_clock WHERE id = 1")).scalar_one()
    return row


def build_clock(
    settings: Settings,
    conn: Connection | None = None,
    wall: Callable[[], datetime] = _wall_now,
) -> Clock:
    if settings.clock_mode == "frozen":
        return FrozenClock(settings.app_now)
    if conn is None:
        return RunningClock(settings.app_now)
    wall_now = wall()
    elapsed = wall_now - clock_start(conn, settings.app_now, wall_now)
    return RunningClock(settings.app_now + max(elapsed, timedelta(0)))


@lru_cache
def get_clock() -> Clock:
    """FastAPI dependency. Tests override it with a FrozenClock."""
    from app.db import get_engine  # avoid an import cycle at module load

    settings = get_settings()
    if settings.clock_mode == "frozen":
        return build_clock(settings)
    with get_engine().begin() as conn:
        return build_clock(settings, conn)
