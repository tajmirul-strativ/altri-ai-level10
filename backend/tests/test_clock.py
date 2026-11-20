"""The app's only source of "now" (design.md §2)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.clock import FrozenClock, RunningClock, build_clock
from app.config import Settings

SEED_NOW = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)


class FakeMonotonic:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value


def test_frozen_clock_always_returns_the_same_instant() -> None:
    clock = FrozenClock(SEED_NOW)

    assert clock.now() == SEED_NOW
    assert clock.now() == SEED_NOW


def test_frozen_clock_can_be_moved_by_tests() -> None:
    clock = FrozenClock(SEED_NOW)

    clock.advance(timedelta(minutes=5))
    assert clock.now() == SEED_NOW + timedelta(minutes=5)

    clock.set(datetime(2026, 11, 9, 5, 59, tzinfo=UTC))
    assert clock.now() == datetime(2026, 11, 9, 5, 59, tzinfo=UTC)


def test_running_clock_starts_at_anchor_and_advances_in_real_time() -> None:
    tick = FakeMonotonic()
    clock = RunningClock(SEED_NOW, monotonic=tick)

    assert clock.now() == SEED_NOW

    tick.value += 90.5
    assert clock.now() == SEED_NOW + timedelta(seconds=90.5)


@pytest.mark.parametrize("clock_cls", [FrozenClock, RunningClock])
def test_clocks_reject_naive_datetimes(clock_cls: type) -> None:
    with pytest.raises(ValueError, match="time zone"):
        clock_cls(datetime(2026, 11, 11, 15, 0))


@pytest.mark.parametrize("clock_cls", [FrozenClock, RunningClock])
def test_clocks_return_utc(clock_cls: type) -> None:
    chicago_9am = datetime.fromisoformat("2026-11-11T09:00:00-06:00")

    now = clock_cls(chicago_9am).now()

    assert now == SEED_NOW
    assert now.utcoffset() == timedelta(0)


def test_settings_default_app_now_is_the_seed_now() -> None:
    assert Settings().app_now == SEED_NOW


def test_settings_parse_app_now_with_z_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NOW", "2026-11-09T05:59:00Z")

    assert Settings().app_now == datetime(2026, 11, 9, 5, 59, tzinfo=UTC)


def test_build_clock_frozen_mode() -> None:
    clock = build_clock(Settings(clock_mode="frozen", app_now=SEED_NOW))

    assert isinstance(clock, FrozenClock)
    assert clock.now() == SEED_NOW


def test_build_clock_running_mode_starts_at_app_now() -> None:
    clock = build_clock(Settings(clock_mode="running", app_now=SEED_NOW))

    assert isinstance(clock, RunningClock)
    assert SEED_NOW <= clock.now() < SEED_NOW + timedelta(seconds=5)
