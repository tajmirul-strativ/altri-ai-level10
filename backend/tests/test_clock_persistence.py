"""The running clock survives API restarts (build-log 2026-11-21).

Before: each restart reset "now" to APP_NOW, so rows created after a restart got timestamps
earlier than rows from before it, and live meeting timers froze. Now the moment the clock
started (wall time) is stored once per APP_NOW, and every process resumes from it.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.clock import RunningClock, build_clock, clock_start
from app.config import Settings

SEED_NOW = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)
WALL = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)  # a real-world moment, unrelated to APP_NOW


def test_first_start_records_the_wall_time(db: Session) -> None:
    started = clock_start(db.connection(), SEED_NOW, WALL)

    assert started == WALL


def test_restart_resumes_from_the_recorded_start(db: Session) -> None:
    clock_start(db.connection(), SEED_NOW, WALL)

    later = clock_start(db.connection(), SEED_NOW, WALL + timedelta(minutes=25))

    assert later == WALL


def test_changing_app_now_starts_a_new_clock(db: Session) -> None:
    clock_start(db.connection(), SEED_NOW, WALL)
    other_now = datetime(2026, 11, 16, 15, 0, tzinfo=UTC)

    started = clock_start(db.connection(), other_now, WALL + timedelta(hours=1))

    assert started == WALL + timedelta(hours=1)


def test_build_clock_resumes_after_restart(db: Session) -> None:
    settings = Settings(clock_mode="running", app_now=SEED_NOW)
    build_clock(settings, db.connection(), wall=lambda: WALL)

    # 25 minutes later the API restarts and builds its clock again.
    clock = build_clock(settings, db.connection(), wall=lambda: WALL + timedelta(minutes=25))

    assert isinstance(clock, RunningClock)
    assert (
        SEED_NOW + timedelta(minutes=25)
        <= clock.now()
        < SEED_NOW + timedelta(minutes=25, seconds=5)
    )


def test_frozen_mode_never_touches_the_stored_start(db: Session) -> None:
    build_clock(Settings(clock_mode="frozen", app_now=SEED_NOW), db.connection(), wall=lambda: WALL)

    assert db.execute(text("SELECT count(*) FROM app_clock")).scalar() == 0
