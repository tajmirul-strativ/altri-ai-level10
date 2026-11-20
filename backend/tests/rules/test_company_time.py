"""Weeks, days and quarters in company time (brief 2.6 "Time", design.md §2).

A week runs Monday 00:00:00 to Sunday 23:59:59 in the company time zone and is named by
its Monday. Daylight saving time ended on Sunday 2026-11-01 in Chicago (CDT -5 -> CST -6),
so the seed contains one 169-hour week.
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.company_time import (
    current_week,
    last_closed_week,
    quarter_of,
    shown_weeks,
    today,
    week_bounds,
    week_of,
    week_of_instant,
)

TZ = ZoneInfo("America/Chicago")
SEED_NOW = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)  # Wed Nov 11, 09:00 CST


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


# --- today -------------------------------------------------------------------------------


def test_today_is_the_company_date_of_now() -> None:
    assert today(SEED_NOW, TZ) == date(2026, 11, 11)


def test_today_uses_company_time_not_utc() -> None:
    # 05:59Z on Nov 11 is still 23:59 on Nov 10 in Chicago.
    assert today(utc("2026-11-11T05:59:00Z"), TZ) == date(2026, 11, 10)
    assert today(utc("2026-11-11T06:00:00Z"), TZ) == date(2026, 11, 11)


# --- week_of (calendar dates) ------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "monday"),
    [
        (date(2026, 11, 9), date(2026, 11, 9)),  # Monday is its own week start
        (date(2026, 11, 11), date(2026, 11, 9)),  # Wednesday
        (date(2026, 11, 15), date(2026, 11, 9)),  # Sunday belongs to the week before it
        (date(2026, 11, 1), date(2026, 10, 26)),  # t12's due date (a Sunday)
    ],
)
def test_week_of_returns_the_monday(day: date, monday: date) -> None:
    assert week_of(day) == monday


# --- week_of_instant (UTC timestamps) ----------------------------------------------------


@pytest.mark.parametrize(
    ("instant", "monday"),
    [
        # After DST ended (CST, UTC-6): the week flips at 06:00Z.
        ("2026-11-09T05:59:00Z", date(2026, 11, 2)),  # t28: Sun Nov 8 23:59 CST
        ("2026-11-09T06:00:00Z", date(2026, 11, 9)),  # Mon Nov 9 00:00 CST
        ("2026-11-09T06:01:00Z", date(2026, 11, 9)),  # t29: Mon Nov 9 00:01 CST
        # Before DST ended (CDT, UTC-5): the week flips at 05:00Z.
        ("2026-10-26T04:59:59Z", date(2026, 10, 19)),
        ("2026-10-26T05:00:00Z", date(2026, 10, 26)),
        # The night DST ended: t11 was done Sun Nov 1 23:30 CST.
        ("2026-11-02T05:30:00Z", date(2026, 10, 26)),
    ],
)
def test_week_of_instant_uses_company_time(instant: str, monday: date) -> None:
    assert week_of_instant(utc(instant), TZ) == monday


# --- week_bounds -------------------------------------------------------------------------


def test_week_bounds_are_monday_midnight_to_next_monday_midnight_in_utc() -> None:
    start, end = week_bounds(date(2026, 11, 2), TZ)

    assert start == utc("2026-11-02T06:00:00Z")
    assert end == utc("2026-11-09T06:00:00Z")


def test_week_bounds_across_dst_change_is_169_hours() -> None:
    start, end = week_bounds(date(2026, 10, 26), TZ)

    assert start == utc("2026-10-26T05:00:00Z")  # CDT
    assert end == utc("2026-11-02T06:00:00Z")  # CST
    assert end - start == timedelta(hours=169)


def test_week_bounds_rejects_a_non_monday() -> None:
    with pytest.raises(ValueError):
        week_bounds(date(2026, 11, 3), TZ)


# --- current / last closed / shown weeks -------------------------------------------------


def test_current_and_last_closed_week_at_seed_now() -> None:
    assert current_week(SEED_NOW, TZ) == date(2026, 11, 9)
    assert last_closed_week(SEED_NOW, TZ) == date(2026, 11, 2)


def test_current_week_flips_at_monday_midnight_company_time() -> None:
    assert current_week(utc("2026-11-09T05:59:59Z"), TZ) == date(2026, 11, 2)
    assert current_week(utc("2026-11-09T06:00:00Z"), TZ) == date(2026, 11, 9)


def test_shown_weeks_are_13_mondays_ending_with_the_current_week() -> None:
    weeks = shown_weeks(SEED_NOW, TZ)

    assert len(weeks) == 13
    assert weeks[0] == date(2026, 8, 17)
    assert weeks[-1] == date(2026, 11, 9)
    assert all(w.weekday() == 0 for w in weeks)
    assert all(b - a == timedelta(days=7) for a, b in zip(weeks, weeks[1:], strict=False))


# --- quarter -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "quarter"),
    [
        (date(2026, 11, 11), "2026-Q4"),
        (date(2026, 10, 1), "2026-Q4"),
        (date(2026, 9, 30), "2026-Q3"),
        (date(2026, 1, 1), "2026-Q1"),
        (date(2026, 3, 31), "2026-Q1"),
        (date(2026, 4, 1), "2026-Q2"),
        (date(2026, 12, 31), "2026-Q4"),
    ],
)
def test_quarter_of_is_the_calendar_quarter(day: date, quarter: str) -> None:
    assert quarter_of(day) == quarter
