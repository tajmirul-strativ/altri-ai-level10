"""Shared test fixtures.

Database strategy
- One test database (`l10_test`) is dropped, recreated, migrated and seeded (committed) once
  per test session, so every test sees the seed exactly as `docker compose up` loads it.
- Each test runs inside a transaction that is rolled back afterwards, so every test starts
  from the fresh seed. Code under test may call `session.commit()`: the session joins the
  outer transaction through a SAVEPOINT, so the commit never reaches the database.
- Tests that need real commits (concurrency) use their own scratch database
  (tests/api/test_concurrency.py).

Clock strategy
- Every test runs on a FrozenClock set to the seed's APP_NOW (`clock` fixture).
  A test moves it with `clock.set(...)` / `clock.advance(...)`, e.g. to one minute
  before a week boundary. The API sees the same clock through the get_clock override.

Point `TEST_DATABASE_URL` at any Postgres server the tests may drop and recreate a database on.
"""

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.clock import FrozenClock, get_clock
from app.db import get_db
from app.main import app
from app.seed import load_seed, read_seed
from tests.dbutil import alembic, recreate_database

SEED_NOW = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)  # the seed's APP_NOW

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://l10:l10@localhost:5433/l10_test"
)

ApiFactory = Callable[[str | None], TestClient]


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    recreate_database(TEST_DATABASE_URL)
    eng = create_engine(TEST_DATABASE_URL)
    with eng.begin() as conn:
        alembic(conn, "upgrade", "head")
    with Session(eng) as session:
        load_seed(session, read_seed())
        session.commit()
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
    """Anonymous API client sharing the test's rolled-back session and frozen clock."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_clock] = lambda: clock
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def api(client: TestClient) -> Iterator[ApiFactory]:
    """`api("u2")` returns a client signed in as seeded user u2; `api(None)` is anonymous.

    Each user gets their own client (own cookie jar), all sharing the same session and clock.
    """
    clients: list[TestClient] = []

    def make(user_id: str | None) -> TestClient:
        c = TestClient(app)
        clients.append(c)
        if user_id is not None:
            response = c.post("/api/auth/login", json={"user_id": user_id})
            assert response.status_code == 200, response.text
        return c

    yield make
    for c in clients:
        c.close()
