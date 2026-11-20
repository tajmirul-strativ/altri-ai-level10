"""Database constraints reject invalid data (brief 2.7 "Data integrity", design.md §3).

Rows are inserted with plain SQL, not ORM models, so these tests check the database itself.
A small valid baseline (`world`) is inserted first; each test changes exactly one thing from a
valid row and asserts the Postgres error class:

    23502 not_null_violation   23503 foreign_key_violation
    23505 unique_violation     23514 check_violation (CHECK constraints and our triggers)

Ids are prefixed `x_` so they never collide with seed data.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

NOT_NULL, FOREIGN_KEY, UNIQUE, CHECK = "23502", "23503", "23505", "23514"

T0 = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)

Insert = Callable[..., None]


def _insert(db: Session, table: str, values: dict[str, Any]) -> None:
    cols = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({params})"), values)


def assert_rejected(db: Session, sqlstate: str, table: str, **values: Any) -> None:
    with pytest.raises(IntegrityError) as exc, db.begin_nested():
        _insert(db, table, values)
    assert exc.value.orig.sqlstate == sqlstate, exc.value.orig  # type: ignore[union-attr]


def assert_accepted(db: Session, table: str, **values: Any) -> None:
    with db.begin_nested():
        _insert(db, table, values)


# --- valid rows, overridable per test ------------------------------------------------------


def measurable(**over: Any) -> dict[str, Any]:
    row = dict(
        id="x_m2",
        team_id="x_ta",
        name="Leads",
        owner_id="x_mem",
        unit="count",
        goal_type="at_least",
        goal_value=10,
        goal_min=None,
        goal_max=None,
    )
    return row | over


def score(**over: Any) -> dict[str, Any]:
    row = dict(measurable_id="x_m1", week_start="2026-11-02", value=12)
    return row | over


def rock(**over: Any) -> dict[str, Any]:
    row = dict(
        id="x_r2",
        team_id="x_ta",
        title="Ship it",
        owner_id="x_mem",
        quarter="2026-Q4",
        status="on_track",
    )
    return row | over


def issue(**over: Any) -> dict[str, Any]:
    row = dict(
        id="x_i2",
        team_id="x_ta",
        title="Problem",
        owner_id="x_mem",
        priority=None,
        created_at=T0,
        solved_at=None,
        resolution_note=None,
        source_measurable_id=None,
        source_week_start=None,
    )
    return row | over


def todo(**over: Any) -> dict[str, Any]:
    row = dict(
        id="x_t2",
        team_id="x_ta",
        title="Task",
        owner_id="x_mem",
        due_date="2026-11-11",
        done_at=None,
        source_issue_id=None,
        created_at=T0,
    )
    return row | over


def meeting(**over: Any) -> dict[str, Any]:
    row = dict(
        id="x_mt2",
        team_id="x_ta",
        facilitator_id="x_mem",
        started_at=T0,
        ended_at=None,
        section="scorecard",
        section_started_at=T0,
    )
    return row | over


@pytest.fixture
def world(db: Session) -> Session:
    """Two teams. x_admin (Admin) is in no team; x_obs is an Observer in team A."""
    rows: list[tuple[str, dict[str, Any]]] = [
        ("companies", dict(id="x_co", name="Test Co", timezone="America/Chicago")),
        (
            "users",
            dict(id="x_admin", company_id="x_co", name="Ad", email="ad@x.test", role="admin"),
        ),
        (
            "users",
            dict(id="x_mem", company_id="x_co", name="Me", email="me@x.test", role="team_member"),
        ),
        (
            "users",
            dict(id="x_obs", company_id="x_co", name="Ob", email="ob@x.test", role="observer"),
        ),
        (
            "users",
            dict(id="x_other", company_id="x_co", name="Ot", email="ot@x.test", role="team_member"),
        ),
        ("teams", dict(id="x_ta", company_id="x_co", name="Team A")),
        ("teams", dict(id="x_tb", company_id="x_co", name="Team B")),
        ("team_memberships", dict(team_id="x_ta", user_id="x_mem")),
        ("team_memberships", dict(team_id="x_ta", user_id="x_obs")),
        ("team_memberships", dict(team_id="x_tb", user_id="x_other")),
        ("measurables", measurable(id="x_m1")),
        ("measurables", measurable(id="x_mb", team_id="x_tb", owner_id="x_other")),
        ("rocks", rock(id="x_r1")),
        ("issues", issue(id="x_i1")),
        ("meetings", meeting(id="x_mt1", ended_at=T0 + timedelta(hours=1), section="conclude")),
        ("meeting_attendees", dict(meeting_id="x_mt1", user_id="x_mem", joined_at=T0)),
        ("meeting_attendees", dict(meeting_id="x_mt1", user_id="x_obs", joined_at=T0)),
    ]
    for table, values in rows:
        _insert(db, table, values)
    db.flush()
    return db


# =========================================================================================
# Users and memberships
# =========================================================================================


def test_user_role_must_be_known(world: Session) -> None:
    assert_rejected(
        world, CHECK, "users", id="x_u", company_id="x_co", name="U", email="u@x.test", role="owner"
    )


def test_user_email_is_unique(world: Session) -> None:
    assert_rejected(
        world,
        UNIQUE,
        "users",
        id="x_u",
        company_id="x_co",
        name="U",
        email="me@x.test",
        role="observer",
    )


def test_membership_is_unique(world: Session) -> None:
    assert_rejected(world, UNIQUE, "team_memberships", team_id="x_ta", user_id="x_mem")


def test_membership_needs_existing_user(world: Session) -> None:
    assert_rejected(world, FOREIGN_KEY, "team_memberships", team_id="x_ta", user_id="x_ghost")


# =========================================================================================
# Measurables and scores
# =========================================================================================


@pytest.mark.parametrize(
    "goal",
    [
        dict(goal_type="at_least", goal_value=10),
        dict(goal_type="at_most", goal_value=3.0),
        dict(goal_type="exactly", goal_value=1),
        dict(goal_type="between", goal_value=None, goal_min=2, goal_max=4),
        dict(goal_type="between", goal_value=None, goal_min=3, goal_max=3),
    ],
)
def test_valid_goals_are_accepted(world: Session, goal: dict[str, Any]) -> None:
    assert_accepted(world, "measurables", **measurable(**goal))


@pytest.mark.parametrize(
    "goal",
    [
        dict(goal_type="above", goal_value=10),  # unknown type
        dict(goal_type="at_least", goal_value=None),  # missing value
        dict(goal_type="at_least", goal_value=10, goal_min=1),  # stray min
        dict(goal_type="between", goal_value=None, goal_min=2, goal_max=None),  # missing max
        dict(goal_type="between", goal_value=3, goal_min=2, goal_max=4),  # stray value
        dict(goal_type="between", goal_value=None, goal_min=5, goal_max=4),  # min > max
    ],
)
def test_malformed_goals_are_rejected(world: Session, goal: dict[str, Any]) -> None:
    assert_rejected(world, CHECK, "measurables", **measurable(**goal))


def test_measurable_owner_must_be_team_member(world: Session) -> None:
    assert_rejected(world, FOREIGN_KEY, "measurables", **measurable(owner_id="x_other"))


def test_measurable_owner_cannot_be_observer(world: Session) -> None:
    assert_rejected(world, CHECK, "measurables", **measurable(owner_id="x_obs"))


def test_score_is_accepted_for_a_monday(world: Session) -> None:
    assert_accepted(world, "scores", **score())


def test_score_week_must_be_a_monday(world: Session) -> None:
    assert_rejected(world, CHECK, "scores", **score(week_start="2026-11-03"))


def test_one_score_per_measurable_per_week(world: Session) -> None:
    assert_accepted(world, "scores", **score())
    assert_rejected(world, UNIQUE, "scores", **score(value=13))


def test_score_value_is_required(world: Session) -> None:
    assert_rejected(world, NOT_NULL, "scores", **score(value=None))


def test_score_keeps_exact_decimals(world: Session) -> None:
    assert_accepted(world, "scores", **score(value="3.1"))

    stored = world.execute(
        text("SELECT value::text FROM scores WHERE measurable_id = 'x_m1'")
    ).scalar()

    assert stored in {"3.1", "3.10", "3.100"}  # NUMERIC, not a binary float


# =========================================================================================
# Rocks and milestones
# =========================================================================================


@pytest.mark.parametrize("quarter", ["2026-Q5", "2026-Q0", "Q4-2026", "2026Q4", "26-Q4"])
def test_rock_quarter_format(world: Session, quarter: str) -> None:
    assert_rejected(world, CHECK, "rocks", **rock(quarter=quarter))


def test_rock_status_must_be_known(world: Session) -> None:
    assert_rejected(world, CHECK, "rocks", **rock(status="done"))


def test_rock_owner_must_be_team_member(world: Session) -> None:
    assert_rejected(world, FOREIGN_KEY, "rocks", **rock(owner_id="x_other"))


def test_milestone_needs_existing_rock(world: Session) -> None:
    assert_rejected(
        world,
        FOREIGN_KEY,
        "milestones",
        id="x_ms",
        rock_id="x_ghost",
        title="Step",
        due_date="2026-12-01",
        done=False,
    )


# =========================================================================================
# Issues
# =========================================================================================


@pytest.mark.parametrize("priority", [None, 1, 5])
def test_issue_priority_none_or_1_to_5_is_accepted(world: Session, priority: int | None) -> None:
    assert_accepted(world, "issues", **issue(priority=priority))


@pytest.mark.parametrize("priority", [0, 6, -1])
def test_issue_priority_out_of_range_is_rejected(world: Session, priority: int) -> None:
    assert_rejected(world, CHECK, "issues", **issue(priority=priority))


@pytest.mark.parametrize("title", ["", "   "])
def test_issue_title_cannot_be_blank(world: Session, title: str) -> None:
    assert_rejected(world, CHECK, "issues", **issue(title=title))


def test_issue_title_is_required(world: Session) -> None:
    assert_rejected(world, NOT_NULL, "issues", **issue(title=None))


def test_solved_issue_with_note_is_accepted(world: Session) -> None:
    solved = issue(solved_at=T0 + timedelta(hours=1), resolution_note="Fixed it.")
    assert_accepted(world, "issues", **solved)


def test_solved_issue_needs_a_note(world: Session) -> None:
    assert_rejected(world, CHECK, "issues", **issue(solved_at=T0 + timedelta(hours=1)))


def test_note_without_solved_time_is_rejected(world: Session) -> None:
    assert_rejected(world, CHECK, "issues", **issue(resolution_note="Fixed it."))


def test_resolution_note_cannot_be_blank(world: Session) -> None:
    blank = issue(solved_at=T0 + timedelta(hours=1), resolution_note="  ")
    assert_rejected(world, CHECK, "issues", **blank)


def test_issue_cannot_be_solved_before_it_was_created(world: Session) -> None:
    early = issue(solved_at=T0 - timedelta(minutes=1), resolution_note="Fixed it.")
    assert_rejected(world, CHECK, "issues", **early)


def test_issue_source_is_both_columns_or_neither(world: Session) -> None:
    assert_rejected(world, CHECK, "issues", **issue(source_measurable_id="x_m1"))
    assert_rejected(world, CHECK, "issues", **issue(source_week_start="2026-11-02"))


def test_issue_source_must_be_a_monday(world: Session) -> None:
    bad = issue(source_measurable_id="x_m1", source_week_start="2026-11-03")
    assert_rejected(world, CHECK, "issues", **bad)


def test_issue_source_measurable_must_be_in_same_team(world: Session) -> None:
    other_team = issue(source_measurable_id="x_mb", source_week_start="2026-11-02")
    assert_rejected(world, FOREIGN_KEY, "issues", **other_team)


def test_issue_owner_cannot_be_observer(world: Session) -> None:
    assert_rejected(world, CHECK, "issues", **issue(owner_id="x_obs"))


def test_issue_owner_must_be_member_or_admin(world: Session) -> None:
    assert_rejected(world, CHECK, "issues", **issue(owner_id="x_other"))


def test_admin_outside_team_may_own_issue(world: Session) -> None:
    assert_accepted(world, "issues", **issue(owner_id="x_admin"))


# --- no duplicate open Issue per Measurable and week ----------------------------------------

CELL = dict(source_measurable_id="x_m1", source_week_start="2026-11-02")
SOLVED = dict(solved_at=T0 + timedelta(hours=1), resolution_note="Done.")


def test_two_open_issues_for_same_cell_are_rejected(world: Session) -> None:
    assert_accepted(world, "issues", **issue(id="x_i2", **CELL))
    assert_rejected(world, UNIQUE, "issues", **issue(id="x_i3", **CELL))


def test_open_issue_allowed_once_previous_one_is_solved(world: Session) -> None:
    assert_accepted(world, "issues", **issue(id="x_i2", **CELL, **SOLVED))
    assert_accepted(world, "issues", **issue(id="x_i3", **CELL))


def test_several_solved_issues_for_same_cell_are_allowed(world: Session) -> None:
    assert_accepted(world, "issues", **issue(id="x_i2", **CELL, **SOLVED))
    assert_accepted(world, "issues", **issue(id="x_i3", **CELL, **SOLVED))


def test_open_issues_for_different_weeks_are_allowed(world: Session) -> None:
    assert_accepted(world, "issues", **issue(id="x_i2", **CELL))
    next_week = CELL | dict(source_week_start="2026-11-09")
    assert_accepted(world, "issues", **issue(id="x_i3", **next_week))


def test_reopening_a_duplicate_by_update_is_rejected(world: Session) -> None:
    assert_accepted(world, "issues", **issue(id="x_i2", **CELL, **SOLVED))
    assert_accepted(world, "issues", **issue(id="x_i3", **CELL))

    with pytest.raises(IntegrityError) as exc, world.begin_nested():
        world.execute(
            text("UPDATE issues SET solved_at = NULL, resolution_note = NULL WHERE id = 'x_i2'")
        )
    assert exc.value.orig.sqlstate == UNIQUE  # type: ignore[union-attr]


# =========================================================================================
# To-Dos
# =========================================================================================


def test_valid_todo_linked_to_issue_is_accepted(world: Session) -> None:
    assert_accepted(world, "todos", **todo(source_issue_id="x_i1"))


@pytest.mark.parametrize("title", ["", "   "])
def test_todo_title_cannot_be_blank(world: Session, title: str) -> None:
    assert_rejected(world, CHECK, "todos", **todo(title=title))


def test_todo_due_date_is_required(world: Session) -> None:
    assert_rejected(world, NOT_NULL, "todos", **todo(due_date=None))


def test_todo_owner_must_be_team_member(world: Session) -> None:
    # Agreed rule: only the team's own Admins and Team Members, so a non-member Admin can't.
    assert_rejected(world, FOREIGN_KEY, "todos", **todo(owner_id="x_admin"))


def test_todo_owner_cannot_be_observer(world: Session) -> None:
    assert_rejected(world, CHECK, "todos", **todo(owner_id="x_obs"))


def test_todo_source_issue_must_be_in_same_team(world: Session) -> None:
    assert_accepted(world, "issues", **issue(id="x_ib", team_id="x_tb", owner_id="x_other"))
    assert_rejected(world, FOREIGN_KEY, "todos", **todo(source_issue_id="x_ib"))


# =========================================================================================
# Meetings
# =========================================================================================


def test_active_meeting_is_accepted(world: Session) -> None:
    assert_accepted(world, "meetings", **meeting())


def test_one_active_meeting_per_team(world: Session) -> None:
    assert_accepted(world, "meetings", **meeting(id="x_mt2"))
    assert_rejected(world, UNIQUE, "meetings", **meeting(id="x_mt3"))


def test_active_meetings_in_different_teams_are_allowed(world: Session) -> None:
    assert_accepted(world, "meetings", **meeting(id="x_mt2"))
    assert_accepted(
        world, "meetings", **meeting(id="x_mt3", team_id="x_tb", facilitator_id="x_other")
    )


def test_section_must_be_known(world: Session) -> None:
    assert_rejected(world, CHECK, "meetings", **meeting(section="headlines"))


def test_meeting_cannot_end_before_it_starts(world: Session) -> None:
    assert_rejected(world, CHECK, "meetings", **meeting(ended_at=T0 - timedelta(minutes=1)))


def test_facilitator_cannot_be_observer(world: Session) -> None:
    assert_rejected(world, CHECK, "meetings", **meeting(facilitator_id="x_obs"))


def test_facilitator_must_be_member_or_admin(world: Session) -> None:
    assert_rejected(world, CHECK, "meetings", **meeting(facilitator_id="x_other"))


def test_admin_outside_team_may_facilitate(world: Session) -> None:
    assert_accepted(world, "meetings", **meeting(facilitator_id="x_admin"))


# --- attendees -----------------------------------------------------------------------------


def test_attendee_is_unique_per_meeting(world: Session) -> None:
    assert_rejected(
        world, UNIQUE, "meeting_attendees", meeting_id="x_mt1", user_id="x_mem", joined_at=T0
    )


def test_admin_outside_team_may_attend(world: Session) -> None:
    assert_accepted(world, "meeting_attendees", meeting_id="x_mt1", user_id="x_admin", joined_at=T0)


def test_attendee_must_be_member_or_admin(world: Session) -> None:
    assert_rejected(
        world, CHECK, "meeting_attendees", meeting_id="x_mt1", user_id="x_other", joined_at=T0
    )


# --- ratings -------------------------------------------------------------------------------


@pytest.mark.parametrize("rating", [1, 10])
def test_rating_1_to_10_is_accepted(world: Session, rating: int) -> None:
    assert_accepted(world, "meeting_ratings", meeting_id="x_mt1", user_id="x_mem", rating=rating)


@pytest.mark.parametrize("rating", [0, 11])
def test_rating_out_of_range_is_rejected(world: Session, rating: int) -> None:
    assert_rejected(
        world, CHECK, "meeting_ratings", meeting_id="x_mt1", user_id="x_mem", rating=rating
    )


def test_one_rating_per_attendee(world: Session) -> None:
    assert_accepted(world, "meeting_ratings", meeting_id="x_mt1", user_id="x_mem", rating=8)
    assert_rejected(world, UNIQUE, "meeting_ratings", meeting_id="x_mt1", user_id="x_mem", rating=9)


def test_only_attendees_can_rate(world: Session) -> None:
    assert_rejected(
        world, FOREIGN_KEY, "meeting_ratings", meeting_id="x_mt1", user_id="x_admin", rating=8
    )


def test_observer_attendee_cannot_rate(world: Session) -> None:
    assert_rejected(world, CHECK, "meeting_ratings", meeting_id="x_mt1", user_id="x_obs", rating=8)
