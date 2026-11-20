"""Migrations apply cleanly and can be rolled back (brief 2.7 "Postgres with migrations")."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.engine import make_url

from tests.conftest import TEST_DATABASE_URL
from tests.dbutil import alembic, drop_database, recreate_database

TABLES = {
    "companies",
    "users",
    "teams",
    "team_memberships",
    "measurables",
    "scores",
    "rocks",
    "milestones",
    "issues",
    "todos",
    "meetings",
    "meeting_attendees",
    "meeting_ratings",
    "app_clock",
}


@pytest.fixture
def scratch_engine() -> Iterator[Engine]:
    """A throwaway database, separate from the shared test database."""
    url = (
        make_url(TEST_DATABASE_URL)
        .set(database="l10_migration_check")
        .render_as_string(hide_password=False)
    )
    recreate_database(url)
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()
        drop_database(url)


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_creates_every_table(scratch_engine: Engine) -> None:
    with scratch_engine.begin() as conn:
        alembic(conn, "upgrade", "head")

    assert _tables(scratch_engine) == TABLES


def test_downgrade_to_base_then_upgrade_again(scratch_engine: Engine) -> None:
    with scratch_engine.begin() as conn:
        alembic(conn, "upgrade", "head")
    with scratch_engine.begin() as conn:
        alembic(conn, "downgrade", "base")

    assert _tables(scratch_engine) == set()

    with scratch_engine.begin() as conn:
        alembic(conn, "upgrade", "head")

    assert _tables(scratch_engine) == TABLES
