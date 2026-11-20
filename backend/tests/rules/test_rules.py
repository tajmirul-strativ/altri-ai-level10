"""Business rules from brief 2.6, each with its boundary cases (design.md §4).

The rules are pure functions: every input, including "now" and "today", is passed in.
Examples reuse seed records (ids in comments) wherever the seed already sits on a boundary.

"No duplicate Issues" is not a pure function; it is tested at the database and API layers.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D
from zoneinfo import ZoneInfo

import pytest

from app.rules import (
    Completion,
    Goal,
    IssueFacts,
    MilestoneFacts,
    TodoFacts,
    is_overdue,
    measurable_status,
    meeting_rating,
    order_issues,
    percent,
    rock_progress,
    rock_status,
    scorecard_week,
    todo_completion,
)

TZ = ZoneInfo("America/Chicago")
SEED_NOW = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)
TODAY = date(2026, 11, 11)
CURRENT_WEEK = date(2026, 11, 9)
CLOSED_WEEK = date(2026, 11, 2)


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


# =========================================================================================
# Rounding: half up, never banker's rounding or floats
# =========================================================================================


@pytest.mark.parametrize(
    ("part", "whole", "expected"),
    [
        (1, 8, 13),  # 12.5 -> 13 (Python's round() gives 12)
        (1, 3, 33),
        (2, 3, 67),
        (1, 200, 1),  # 0.5 -> 1
        (9, 10, 90),
        (0, 5, 0),
        (5, 5, 100),
    ],
)
def test_percent_rounds_half_up(part: int, whole: int, expected: int) -> None:
    assert percent(part, whole) == expected


# =========================================================================================
# Measurable status
# =========================================================================================

AT_LEAST_10 = Goal(type="at_least", value=D("10"))  # m1 New deals closed
AT_MOST_3 = Goal(type="at_most", value=D("3.0"))  # m2 Customer churn
BETWEEN_2_4 = Goal(type="between", min=D("2"), max=D("4"))  # m3 Avg first response
EXACTLY_1 = Goal(type="exactly", value=D("1"))  # m4 Payroll runs


@pytest.mark.parametrize(
    ("goal", "score", "expected"),
    [
        (AT_LEAST_10, D("10"), "on_track"),  # boundary
        (AT_LEAST_10, D("10.01"), "on_track"),
        (AT_LEAST_10, D("9.99"), "off_track"),
        (AT_MOST_3, D("3.0"), "on_track"),  # boundary (m2, week of Nov 2)
        (AT_MOST_3, D("3"), "on_track"),  # same number, different scale
        (AT_MOST_3, D("3.01"), "off_track"),
        (BETWEEN_2_4, D("2"), "on_track"),  # lower boundary (m3, week of Aug 24)
        (BETWEEN_2_4, D("4"), "on_track"),  # upper boundary (m3, week of Aug 31)
        (BETWEEN_2_4, D("3.2"), "on_track"),
        (BETWEEN_2_4, D("1.99"), "off_track"),
        (BETWEEN_2_4, D("4.01"), "off_track"),
        (EXACTLY_1, D("1"), "on_track"),
        (EXACTLY_1, D("1.0"), "on_track"),
        (EXACTLY_1, D("0"), "off_track"),  # m4, week of Oct 26
        (EXACTLY_1, D("2"), "off_track"),  # m4, week of Sep 21
    ],
)
def test_measurable_status_compares_score_with_goal(goal: Goal, score: D, expected: str) -> None:
    assert measurable_status(goal, score, CLOSED_WEEK, CURRENT_WEEK) == expected


def test_closed_week_without_score_is_off_track() -> None:
    # m5 Cash on hand has no score for the week of Nov 2.
    assert measurable_status(AT_LEAST_10, None, CLOSED_WEEK, CURRENT_WEEK) == "off_track"


def test_current_week_without_score_is_pending() -> None:
    assert measurable_status(AT_LEAST_10, None, CURRENT_WEEK, CURRENT_WEEK) == "pending"


def test_current_week_with_score_is_judged_normally() -> None:
    # m5 has 520 for the current week against "at least 500".
    goal = Goal(type="at_least", value=D("500"))

    assert measurable_status(goal, D("520"), CURRENT_WEEK, CURRENT_WEEK) == "on_track"
    assert measurable_status(goal, D("499"), CURRENT_WEEK, CURRENT_WEEK) == "off_track"


def test_measurable_status_rejects_a_future_week() -> None:
    with pytest.raises(ValueError):
        measurable_status(AT_LEAST_10, D("12"), CURRENT_WEEK + timedelta(days=7), CURRENT_WEEK)


# =========================================================================================
# To-Do completion rate
# =========================================================================================


def todo(due: str, done_at: str | None = None) -> TodoFacts:
    return TodoFacts(
        due_date=date.fromisoformat(due),
        done_at=utc(done_at) if done_at else None,
    )


def test_week_with_nothing_due_has_no_rate() -> None:
    todos = [todo("2026-11-10")]  # due in a different week

    assert todo_completion(todos, CLOSED_WEEK, SEED_NOW, TZ) is None


def test_exactly_90_percent_meets_target() -> None:
    # Leadership, week of Nov 2: 10 due, 9 done in time.
    todos = [todo("2026-11-04", "2026-11-03T20:00:00Z") for _ in range(9)]
    todos.append(todo("2026-11-08"))

    assert todo_completion(todos, CLOSED_WEEK, SEED_NOW, TZ) == Completion(
        due=10, done=9, rate_percent=90, meets_target=True
    )


def test_target_compares_exact_ratio_not_rounded_percent() -> None:
    # 899 / 1000 = 89.9 %, which rounds to 90 but is below target.
    todos = [todo("2026-11-04", "2026-11-03T20:00:00Z") for _ in range(899)]
    todos += [todo("2026-11-04") for _ in range(101)]

    assert todo_completion(todos, CLOSED_WEEK, SEED_NOW, TZ) == Completion(
        due=1000, done=899, rate_percent=90, meets_target=False
    )


def test_rate_rounds_half_up() -> None:
    # 1 of 8 = 12.5 % -> 13 %
    todos = [todo("2026-11-04", "2026-11-03T20:00:00Z")] + [todo("2026-11-04") for _ in range(7)]

    completion = todo_completion(todos, CLOSED_WEEK, SEED_NOW, TZ)

    assert completion is not None
    assert completion.rate_percent == 13


def test_done_on_last_minute_of_due_week_counts() -> None:
    # t28: due Fri Nov 6, done Sun Nov 8 23:59 CST.
    todos = [todo("2026-11-06", "2026-11-09T05:59:00Z")]

    assert todo_completion(todos, CLOSED_WEEK, SEED_NOW, TZ) == Completion(
        due=1, done=1, rate_percent=100, meets_target=True
    )


def test_done_after_due_week_counts_as_not_done() -> None:
    # t29: due Sun Nov 8, done Mon Nov 9 00:01 CST.
    todos = [todo("2026-11-08", "2026-11-09T06:01:00Z")]

    assert todo_completion(todos, CLOSED_WEEK, SEED_NOW, TZ) == Completion(
        due=1, done=0, rate_percent=0, meets_target=False
    )


def test_done_exactly_at_next_monday_midnight_is_late() -> None:
    todos = [todo("2026-11-08", "2026-11-09T06:00:00Z")]  # Mon 00:00:00 CST

    completion = todo_completion(todos, CLOSED_WEEK, SEED_NOW, TZ)

    assert completion is not None
    assert completion.done == 0


def test_week_end_respects_dst_change() -> None:
    # Week of Oct 26 ends Mon Nov 2 00:00 CST = 06:00Z, not 05:00Z.
    week = date(2026, 10, 26)
    on_time = todo("2026-10-30", "2026-11-02T05:30:00Z")  # t11: Sun Nov 1 23:30 CST
    late = todo("2026-10-30", "2026-11-02T06:00:00Z")

    assert todo_completion([on_time], week, SEED_NOW, TZ).done == 1  # type: ignore[union-attr]
    assert todo_completion([late], week, SEED_NOW, TZ).done == 0  # type: ignore[union-attr]


def test_sunday_due_date_belongs_to_the_week_it_ends() -> None:
    # Seed, week of Oct 26: t10 (done), t11 (done), t12 (due Sun Nov 1, not done).
    todos = [
        todo("2026-10-27", "2026-10-26T19:00:00Z"),
        todo("2026-10-30", "2026-11-02T05:30:00Z"),
        todo("2026-11-01"),
    ]

    assert todo_completion(todos, date(2026, 10, 26), SEED_NOW, TZ) == Completion(
        due=3, done=2, rate_percent=67, meets_target=False
    )


def test_done_before_due_week_counts() -> None:
    todos = [todo("2026-11-04", "2026-10-30T15:00:00Z")]  # finished the week before

    assert todo_completion(todos, CLOSED_WEEK, SEED_NOW, TZ).done == 1  # type: ignore[union-attr]


def test_current_week_counts_only_what_is_done_by_now() -> None:
    # Current week (Nov 9): one done before now, one "done" after now.
    todos = [
        todo("2026-11-12", "2026-11-10T15:00:00Z"),
        todo("2026-11-12", "2026-11-12T15:00:00Z"),
        todo("2026-11-13"),
    ]

    assert todo_completion(todos, CURRENT_WEEK, SEED_NOW, TZ) == Completion(
        due=3, done=1, rate_percent=33, meets_target=False
    )


# =========================================================================================
# Overdue To-Dos
# =========================================================================================


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        (todo("2026-11-10"), True),  # t31: due yesterday, not done
        (todo("2026-11-01"), True),  # t12
        (todo("2026-11-11"), False),  # t30: due today is not overdue
        (todo("2026-11-13"), False),  # t32: due later
        (todo("2026-11-01", "2026-11-05T15:00:00Z"), False),  # done late is not overdue
    ],
)
def test_is_overdue(item: TodoFacts, expected: bool) -> None:
    assert is_overdue(item, TODAY) is expected


# =========================================================================================
# Rock status
# =========================================================================================


def milestone(due: str, done: bool = False) -> MilestoneFacts:
    return MilestoneFacts(due_date=date.fromisoformat(due), done=done)


def test_seeded_complete_wins_even_with_past_due_milestone() -> None:
    assert rock_status("complete", [milestone("2026-11-01")], TODAY) == "complete"


def test_seeded_off_track_stays_off_track() -> None:
    # r4: off-track, no Milestones.
    assert rock_status("off_track", [], TODAY) == "off_track"


def test_unfinished_milestone_past_due_makes_rock_off_track() -> None:
    # r2: "Shortlist of 5" was due yesterday and isn't done.
    milestones = [milestone("2026-10-10", done=True), milestone("2026-11-10")]

    assert rock_status("on_track", milestones, TODAY) == "off_track"


def test_milestone_due_today_is_not_past_due() -> None:
    # r1: "Portal beta" is due today.
    milestones = [milestone("2026-10-15", done=True), milestone("2026-11-11")]

    assert rock_status("on_track", milestones, TODAY) == "on_track"


def test_finished_milestone_past_due_does_not_matter() -> None:
    assert rock_status("on_track", [milestone("2026-10-15", done=True)], TODAY) == "on_track"


def test_rock_without_milestones_keeps_seeded_status() -> None:
    # r5 / r7
    assert rock_status("on_track", [], TODAY) == "on_track"


# =========================================================================================
# Rock progress
# =========================================================================================


def test_progress_is_done_over_total_rounded_half_up() -> None:
    # r2: 1 of 8 done = 12.5 % -> 13 %
    milestones = [milestone("2026-10-10", done=True)] + [milestone("2026-12-01")] * 7

    assert rock_progress("on_track", milestones) == 13


def test_progress_one_of_three() -> None:
    # r1: 1 of 3 done
    milestones = [
        milestone("2026-10-15", done=True),
        milestone("2026-11-11"),
        milestone("2026-12-01"),
    ]

    assert rock_progress("on_track", milestones) == 33


def test_progress_all_done_is_100() -> None:
    assert rock_progress("on_track", [milestone("2026-10-15", done=True)] * 2) == 100


@pytest.mark.parametrize(
    ("seeded", "expected"),
    [
        ("on_track", 0),  # r5, r7
        ("off_track", 0),  # r4
        ("complete", 100),  # r3
    ],
)
def test_progress_without_milestones(seeded: str, expected: int) -> None:
    assert rock_progress(seeded, []) == expected


def test_complete_rock_with_milestones_reports_milestone_ratio() -> None:
    # The 100 % rule is only for Rocks without Milestones.
    milestones = [
        milestone("2026-10-15", done=True),
        milestone("2026-11-11"),
        milestone("2026-12-01"),
    ]

    assert rock_progress("complete", milestones) == 33


# =========================================================================================
# Issue order
# =========================================================================================


def issue(issue_id: str, priority: int | None, created_at: str) -> IssueFacts:
    return IssueFacts(id=issue_id, priority=priority, created_at=utc(created_at))


def test_issue_order_matches_seed() -> None:
    issues = [
        issue("i1", 5, "2026-10-20T14:00:00Z"),
        issue("i2", 5, "2026-10-14T16:00:00Z"),
        issue("i3", 3, "2026-10-05T15:00:00Z"),
        issue("i4", None, "2026-09-01T15:00:00Z"),
        issue("i5", 4, "2026-11-09T16:00:00Z"),
    ]

    assert [i.id for i in order_issues(issues)] == ["i2", "i1", "i5", "i3", "i4"]


def test_higher_priority_first_down_to_1() -> None:
    issues = [issue(f"p{p}", p, "2026-11-01T15:00:00Z") for p in (1, 3, 5, 2, 4)]

    assert [i.priority for i in order_issues(issues)] == [5, 4, 3, 2, 1]


def test_no_priority_comes_after_priority_1_even_if_older() -> None:
    issues = [
        issue("none", None, "2026-01-01T00:00:00Z"),
        issue("low", 1, "2026-11-10T00:00:00Z"),
    ]

    assert [i.id for i in order_issues(issues)] == ["low", "none"]


def test_same_priority_oldest_first_including_no_priority() -> None:
    issues = [
        issue("new", None, "2026-11-10T00:00:00Z"),
        issue("old", None, "2026-11-01T00:00:00Z"),
    ]

    assert [i.id for i in order_issues(issues)] == ["old", "new"]


def test_full_tie_is_broken_by_id_for_a_stable_order() -> None:
    issues = [issue("i20", 3, "2026-11-01T00:00:00Z"), issue("i10", 3, "2026-11-01T00:00:00Z")]

    assert [i.id for i in order_issues(issues)] == ["i10", "i20"]


# =========================================================================================
# Meeting rating
# =========================================================================================


@pytest.mark.parametrize(
    ("ratings", "expected"),
    [
        ([8, 9, 8, 8], D("8.3")),  # mt2: 8.25 -> 8.3 (Python's round() gives 8.2)
        ([8, 9, 7], D("8.0")),  # mt1
        ([7, 8, 8, 8], D("7.8")),  # 7.75 -> 7.8
        ([8, 8, 9], D("8.3")),  # 8.333...
        ([9, 9, 8], D("8.7")),  # 8.666...
        ([10], D("10.0")),
        ([1, 2], D("1.5")),
    ],
)
def test_meeting_rating_is_average_to_one_decimal_half_up(ratings: list[int], expected: D) -> None:
    assert meeting_rating(ratings) == expected


def test_no_ratings_means_no_score() -> None:
    assert meeting_rating([]) is None


# =========================================================================================
# Scorecard week of a meeting (the last closed week when it started)
# =========================================================================================


@pytest.mark.parametrize(
    ("started_at", "week"),
    [
        ("2026-10-28T15:00:00Z", date(2026, 10, 19)),  # mt1: Wed Oct 28 10:00 CDT
        ("2026-11-04T15:00:00Z", date(2026, 10, 26)),  # mt2: Wed Nov 4 09:00 CST
        ("2026-11-09T06:30:00Z", date(2026, 11, 2)),  # Mon 00:30 CST: Nov 2 just closed
        ("2026-11-09T05:30:00Z", date(2026, 10, 26)),  # Sun 23:30 CST: still in Nov 2 week
    ],
)
def test_scorecard_week_is_week_before_meeting_start(started_at: str, week: date) -> None:
    assert scorecard_week(utc(started_at), TZ) == week
