"""Business rules from brief 2.6 (design.md §4).

Pure functions: no database and no clock. Callers pass "now", "today" and the company time
zone in. Both the API and the rules report use these functions, so they always agree.

Inputs are described by Protocols, so the small dataclasses below and ORM rows both work.
All rounding is half up with Decimal; floats and round() are never used.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from app.company_time import week_bounds, week_of, week_of_instant

MeasurableStatus = Literal["on_track", "off_track", "pending"]
RockStatus = Literal["on_track", "off_track", "complete"]
GoalType = Literal["at_least", "at_most", "between", "exactly"]

COMPLETION_TARGET_NUM, COMPLETION_TARGET_DEN = 9, 10  # 90 %, compared as an exact fraction


# --- Rounding ------------------------------------------------------------------------------


def percent(part: int, whole: int) -> int:
    """`part / whole` as a whole percent, rounded half up (12.5 % -> 13 %)."""
    if whole <= 0:
        raise ValueError("whole must be positive")
    value = Decimal(part) * 100 / Decimal(whole)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


# --- Measurable status ---------------------------------------------------------------------


@dataclass(frozen=True)
class Goal:
    type: GoalType
    value: Decimal | None = None
    min: Decimal | None = None
    max: Decimal | None = None

    def __post_init__(self) -> None:
        if self.type == "between":
            if self.min is None or self.max is None or self.value is not None:
                raise ValueError("a 'between' goal needs min and max, and no value")
            if self.min > self.max:
                raise ValueError("goal min must not exceed max")
        elif self.value is None or self.min is not None or self.max is not None:
            raise ValueError(f"an '{self.type}' goal needs a value, and no min or max")

    def is_met_by(self, score: Decimal) -> bool:
        """Boundaries count as met."""
        match self.type:
            case "at_least":
                return score >= self.value  # type: ignore[operator]
            case "at_most":
                return score <= self.value  # type: ignore[operator]
            case "exactly":
                return score == self.value
            case "between":
                return self.min <= score <= self.max  # type: ignore[operator]


def measurable_status(
    goal: Goal, score: Decimal | None, week: date, current_week: date
) -> MeasurableStatus:
    """Status of one Scorecard cell.

    A missing score is `pending` in the current week and `off_track` in a closed week.
    """
    if week > current_week:
        raise ValueError(f"week {week} is after the current week {current_week}")
    if score is None:
        return "pending" if week == current_week else "off_track"
    return "on_track" if goal.is_met_by(score) else "off_track"


# --- To-Dos --------------------------------------------------------------------------------


class TodoLike(Protocol):
    @property
    def due_date(self) -> date: ...
    @property
    def done_at(self) -> datetime | None: ...


@dataclass(frozen=True)
class TodoFacts:
    due_date: date
    done_at: datetime | None


@dataclass(frozen=True)
class Completion:
    due: int
    done: int
    rate_percent: int
    meets_target: bool


def todo_completion(
    todos: Iterable[TodoLike], week_start: date, now: datetime, tz: ZoneInfo
) -> Completion | None:
    """To-Dos done by the end of a week ÷ To-Dos due that week. `None` when nothing is due.

    Done after the due week counts as not done. For the current week only what is done by
    `now` counts. The 90 % target compares the exact ratio, not the rounded percent.
    """
    _, week_end = week_bounds(week_start, tz)
    due = [t for t in todos if week_of(t.due_date) == week_start]
    if not due:
        return None
    done = sum(
        1 for t in due if t.done_at is not None and t.done_at < week_end and t.done_at <= now
    )
    return Completion(
        due=len(due),
        done=done,
        rate_percent=percent(done, len(due)),
        meets_target=done * COMPLETION_TARGET_DEN >= len(due) * COMPLETION_TARGET_NUM,
    )


def is_overdue(todo: TodoLike, today: date) -> bool:
    """Not done and due before today (a To-Do due today is not overdue)."""
    return todo.done_at is None and todo.due_date < today


# --- Rocks ---------------------------------------------------------------------------------


class MilestoneLike(Protocol):
    @property
    def due_date(self) -> date: ...
    @property
    def done(self) -> bool: ...


@dataclass(frozen=True)
class MilestoneFacts:
    due_date: date
    done: bool


def rock_status(seeded_status: str, milestones: Sequence[MilestoneLike], today: date) -> RockStatus:
    """Complete if seeded Complete; off-track if seeded Off-track or a Milestone is past due."""
    if seeded_status == "complete":
        return "complete"
    if seeded_status == "off_track":
        return "off_track"
    if any(not m.done and m.due_date < today for m in milestones):
        return "off_track"
    return "on_track"


def rock_progress(seeded_status: str, milestones: Sequence[MilestoneLike]) -> int:
    """Completed ÷ total Milestones as a whole percent. No Milestones: 100 if Complete, else 0."""
    if not milestones:
        return 100 if seeded_status == "complete" else 0
    return percent(sum(1 for m in milestones if m.done), len(milestones))


# --- Issues --------------------------------------------------------------------------------


class IssueLike(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def priority(self) -> int | None: ...
    @property
    def created_at(self) -> datetime: ...


@dataclass(frozen=True)
class IssueFacts:
    id: str
    priority: int | None
    created_at: datetime


def issue_sort_key(issue: IssueLike) -> tuple[bool, int, datetime, str]:
    """Priority 5 first down to 1, no priority last; then oldest first; then id."""
    return (issue.priority is None, -(issue.priority or 0), issue.created_at, issue.id)


def order_issues[IssueT: IssueLike](issues: Iterable[IssueT]) -> list[IssueT]:
    return sorted(issues, key=issue_sort_key)


# --- Meetings ------------------------------------------------------------------------------


def meeting_rating(ratings: Sequence[int]) -> Decimal | None:
    """Average of submitted ratings to one decimal, half up (8.25 -> 8.3). None if no ratings."""
    if not ratings:
        return None
    average = Decimal(sum(ratings)) / Decimal(len(ratings))
    return average.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def scorecard_week(started_at: datetime, tz: ZoneInfo) -> date:
    """The week a meeting reviews: the last closed week when it started."""
    return week_of_instant(started_at, tz) - timedelta(days=7)
