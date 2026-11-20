"""Seed loading (brief 2.7 "Operations": seed data loaded, script safe to rerun).

The seed is loaded inside each test's rolled-back transaction.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.seed import load_seed, read_seed, reset_database

EXPECTED_COUNTS = {
    "companies": 1,
    "users": 9,
    "teams": 3,
    "team_memberships": 11,
    "measurables": 7,
    "scores": 83,
    "rocks": 7,
    "milestones": 12,
    "issues": 9,
    "todos": 20,
    "meetings": 2,
    "meeting_attendees": 10,
    "meeting_ratings": 7,
}


@pytest.fixture(scope="module")
def seed_data() -> dict[str, Any]:
    return read_seed()


def counts(db: Session) -> dict[str, int]:
    return {t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in EXPECTED_COUNTS}


def scalar(db: Session, sql: str) -> Any:
    return db.execute(text(sql)).scalar_one()


def test_load_seed_inserts_every_record(db: Session, seed_data: dict[str, Any]) -> None:
    load_seed(db, seed_data)

    assert counts(db) == EXPECTED_COUNTS


def test_load_seed_keeps_exact_values(db: Session, seed_data: dict[str, Any]) -> None:
    load_seed(db, seed_data)

    assert scalar(
        db, "SELECT value FROM scores WHERE measurable_id='m2' AND week_start='2026-11-02'"
    ) == Decimal("3.0")
    assert scalar(db, "SELECT done_at FROM todos WHERE id='t28'") == datetime(
        2026, 11, 9, 5, 59, tzinfo=UTC
    )
    assert scalar(db, "SELECT goal_min FROM measurables WHERE id='m3'") == Decimal("2")
    assert scalar(db, "SELECT priority FROM issues WHERE id='i4'") is None
    assert scalar(db, "SELECT source_week_start::text FROM issues WHERE id='i5'") == "2026-11-02"
    assert scalar(db, "SELECT timezone FROM companies WHERE id='co_1'") == "America/Chicago"


def test_seeded_meetings_are_ended(db: Session, seed_data: dict[str, Any]) -> None:
    load_seed(db, seed_data)

    assert scalar(db, "SELECT count(*) FROM meetings WHERE ended_at IS NULL") == 0
    assert scalar(db, "SELECT section FROM meetings WHERE id='mt2'") == "conclude"


def test_rerunning_seed_is_safe(db: Session, seed_data: dict[str, Any]) -> None:
    load_seed(db, seed_data)
    load_seed(db, seed_data)

    assert counts(db) == EXPECTED_COUNTS


def test_rerunning_seed_keeps_user_changes(db: Session, seed_data: dict[str, Any]) -> None:
    load_seed(db, seed_data)
    db.execute(text("UPDATE issues SET priority = 1 WHERE id = 'i1'"))
    db.execute(
        text(
            "INSERT INTO issues (team_id, title, owner_id, created_at) "
            "VALUES ('team_lead', 'New one', 'u2', '2026-11-11T15:00:00Z')"
        )
    )

    load_seed(db, seed_data)

    assert scalar(db, "SELECT priority FROM issues WHERE id='i1'") == 1
    assert scalar(db, "SELECT count(*) FROM issues") == 10


def test_new_ids_continue_after_seed_ids(db: Session, seed_data: dict[str, Any]) -> None:
    load_seed(db, seed_data)

    issue_id = scalar(
        db,
        "INSERT INTO issues (team_id, title, owner_id, created_at) "
        "VALUES ('team_lead', 'New', 'u2', '2026-11-11T15:00:00Z') RETURNING id",
    )
    todo_id = scalar(
        db,
        "INSERT INTO todos (team_id, title, owner_id, due_date, created_at) "
        "VALUES ('team_lead', 'New', 'u2', '2026-11-18', '2026-11-11T15:00:00Z') RETURNING id",
    )
    meeting_id = scalar(
        db,
        "INSERT INTO meetings (team_id, facilitator_id, started_at, section, section_started_at) "
        "VALUES ('team_sales', 'u6', '2026-11-11T15:00:00Z', 'scorecard', "
        "'2026-11-11T15:00:00Z') RETURNING id",
    )

    assert (issue_id, todo_id, meeting_id) == ("i10", "t42", "mt3")


def test_reset_restores_the_fresh_seed(db: Session, seed_data: dict[str, Any]) -> None:
    load_seed(db, seed_data)
    db.execute(text("UPDATE issues SET priority = 1 WHERE id = 'i1'"))
    db.execute(
        text(
            "INSERT INTO issues (team_id, title, owner_id, created_at) "
            "VALUES ('team_lead', 'New one', 'u2', '2026-11-11T15:00:00Z')"
        )
    )

    reset_database(db, seed_data)

    assert counts(db) == EXPECTED_COUNTS
    assert scalar(db, "SELECT priority FROM issues WHERE id='i1'") == 5
    next_id = scalar(
        db,
        "INSERT INTO issues (team_id, title, owner_id, created_at) "
        "VALUES ('team_lead', 'New', 'u2', '2026-11-11T15:00:00Z') RETURNING id",
    )
    assert next_id == "i10"
