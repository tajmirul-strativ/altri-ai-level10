"""Shared test fixtures.

Database strategy
- One test database (`l10_test`) is dropped, recreated and migrated once per test session.
- Each test runs inside a transaction that is rolled back afterwards, so every test starts
  from the same state. Code under test may call `session.commit()`: the session joins the
  outer transaction through a SAVEPOINT, so the commit never reaches the database.
- Tests that need real commits (concurrency) get their own fixture later.

Clock strategy
- Every test runs on a FrozenClock set to the seed's APP_NOW (`clock` fixture).
  A test moves it with `clock.set(...)` / `clock.advance(...)`, e.g. to one minute
  before a week boundary. The API sees the same clock through the get_clock override.

Point `TEST_DATABASE_URL` at any Postgres server the tests may drop and recreate a database on.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.clock import FrozenClock, get_clock
from app.db import get_db
from app.main import app
from tests.dbutil import alembic, recreate_database

SEED_NOW = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)  # the seed's APP_NOW

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://l10:l10@localhost:5433/l10_test"
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    recreate_database(TEST_DATABASE_URL)
    eng = create_engine(TEST_DATABASE_URL)
    with eng.begin() as conn:
        alembic(conn, "upgrade", "head")
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back when the test ends."""
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(SEED_NOW)


@pytest.fixture
def client(db: Session, clock: FrozenClock) -> Iterator[TestClient]:
    """API client sharing the test's rolled-back session and frozen clock."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_clock] = lambda: clock
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
