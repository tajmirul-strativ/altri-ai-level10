"""The app's only source of "now" (design.md §2).

Nothing else may call datetime.now(): every rule and timestamp goes through a Clock,
so tests and the rules report can pin time to APP_NOW.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol

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


def build_clock(settings: Settings) -> Clock:
    if settings.clock_mode == "frozen":
        return FrozenClock(settings.app_now)
    return RunningClock(settings.app_now)


@lru_cache
def get_clock() -> Clock:
    """FastAPI dependency. Tests override it with a FrozenClock."""
    return build_clock(get_settings())
