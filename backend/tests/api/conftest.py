"""Fixtures for tests that need real commits: concurrency and live events.

They run against their own scratch database (`l10_committing`), reset to the seed before each
test, instead of the shared rolled-back session.
"""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.clock import FrozenClock, get_clock
from app.db import get_db
from app.main import app
from app.realtime import get_events_dsn
from app.seed import read_seed, reset_database
from tests.conftest import SEED_NOW, TEST_DATABASE_URL
from tests.dbutil import alembic, drop_database, recreate_database

SCRATCH_URL = make_url(TEST_DATABASE_URL).set(database="l10_committing")


@pytest.fixture(scope="module")
def scratch_engine() -> Iterator[Engine]:
    url_text = SCRATCH_URL.render_as_string(hide_password=False)
    recreate_database(url_text)
    engine = create_engine(url_text, pool_size=20, max_overflow=0)
    with engine.begin() as conn:
        alembic(conn, "upgrade", "head")
    yield engine
    engine.dispose()
    drop_database(url_text)


@pytest.fixture
def committing_api(scratch_engine: Engine) -> Iterator[Callable[[str], TestClient]]:
    """Clients whose requests each get their own session and really commit."""
    factory = sessionmaker(bind=scratch_engine, expire_on_commit=False)
    with factory() as db:
        reset_database(db, read_seed())
        db.commit()

    def get_test_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    clock = FrozenClock(SEED_NOW)
    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_events_dsn] = lambda: SCRATCH_URL.set(
        drivername="postgresql"
    ).render_as_string(hide_password=False)
    clients: list[TestClient] = []

    def make(user_id: str) -> TestClient:
        c = TestClient(app)
        clients.append(c)
        assert c.post("/api/auth/login", json={"user_id": user_id}).status_code == 200
        return c

    try:
        yield make
    finally:
        for c in clients:
            c.close()
        app.dependency_overrides.clear()
