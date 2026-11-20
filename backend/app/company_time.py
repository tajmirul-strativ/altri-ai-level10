"""Weeks, days and quarters in company time (brief 2.6 "Time", design.md §2).

A week runs Monday 00:00:00 to Sunday 23:59:59 in the company time zone and is named by its
Monday (`week_start`). All conversions go through zoneinfo, so daylight saving changes
(e.g. the 169-hour week of 2026-10-26 in Chicago) are handled correctly.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

WEEK = timedelta(days=7)
SHOWN_WEEKS = 13


def today(now: datetime, tz: ZoneInfo) -> date:
    """The company calendar date of `now`."""
    return now.astimezone(tz).date()


def week_of(day: date) -> date:
    """The Monday on or before `day`."""
    return day - timedelta(days=day.weekday())


def week_of_instant(instant: datetime, tz: ZoneInfo) -> date:
    """The week (its Monday) that a UTC instant falls in, in company time."""
    return week_of(instant.astimezone(tz).date())


def week_bounds(week_start: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """`[start, end)` of a week as UTC instants: Monday 00:00 to next Monday 00:00 company time."""
    if week_start.weekday() != 0:
        raise ValueError(f"week_start must be a Monday, got {week_start} ({week_start:%A})")
    start = datetime.combine(week_start, time.min, tzinfo=tz)
    end = datetime.combine(week_start + WEEK, time.min, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def current_week(now: datetime, tz: ZoneInfo) -> date:
    return week_of(today(now, tz))


def last_closed_week(now: datetime, tz: ZoneInfo) -> date:
    """The full week before the current one."""
    return current_week(now, tz) - WEEK


def shown_weeks(now: datetime, tz: ZoneInfo) -> list[date]:
    """The 13 weeks on the Scorecard, oldest first, ending with the current week."""
    current = current_week(now, tz)
    return [current - WEEK * back for back in range(SHOWN_WEEKS - 1, -1, -1)]


def quarter_of(day: date) -> str:
    """Calendar quarter, formatted like the seed: `2026-Q4`."""
    return f"{day.year}-Q{(day.month - 1) // 3 + 1}"
