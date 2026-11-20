"""Concurrent requests (brief Part 3: "Concurrent Make it an Issue requests return one Issue").

These need real commits, so they run against their own scratch database, reset to the seed
before each test, instead of the shared rolled-back session.
"""

import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.clock import FrozenClock, get_clock
from app.db import get_db
from app.main import app
from app.models import Measurable, User
from app.seed import read_seed, reset_database
from app.services.issues import make_it_an_issue
from tests.conftest import SEED_NOW, TEST_DATABASE_URL
from tests.dbutil import alembic, drop_database, recreate_database

LEAD = "/api/teams/team_lead"
CELL = f"{LEAD}/measurables/m1/scores/2026-10-26/issue"  # off track, no open Issue
WEEK = date(2026, 10, 26)


@pytest.fixture(scope="module")
def scratch_engine() -> Iterator[Engine]:
    url = make_url(TEST_DATABASE_URL).set(database="l10_concurrency")
    url_text = url.render_as_string(hide_password=False)
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


def run_together(calls: list[Callable[[], object]]) -> list[object]:
    """Release every call at the same moment."""
    barrier = threading.Barrier(len(calls))

    def wrapped(fn: Callable[[], object]) -> object:
        barrier.wait()
        return fn()

    with ThreadPoolExecutor(len(calls)) as pool:
        return list(pool.map(wrapped, calls))


def test_concurrent_make_it_an_issue_returns_one_issue(
    committing_api: Callable[[str], TestClient], scratch_engine: Engine
) -> None:
    clients = [committing_api(u) for u in ("u2", "u3", "u4", "u1") * 3]

    responses = run_together([lambda c=c: c.post(CELL) for c in clients])

    statuses = sorted(r.status_code for r in responses)  # type: ignore[attr-defined]
    ids = {r.json()["id"] for r in responses}  # type: ignore[attr-defined]
    assert statuses == [200] * 11 + [201]
    assert len(ids) == 1
    with scratch_engine.connect() as conn:
        open_for_cell = conn.execute(text(
            "SELECT count(*) FROM issues WHERE source_measurable_id = 'm1' "
            "AND source_week_start = '2026-10-26' AND solved_at IS NULL"
        )).scalar()  # fmt: skip
    assert open_for_cell == 1


def test_concurrent_meeting_starts_create_one_meeting(
    committing_api: Callable[[str], TestClient], scratch_engine: Engine
) -> None:
    clients = [committing_api(u) for u in ("u2", "u3", "u4")]

    responses = run_together([lambda c=c: c.post(f"{LEAD}/meetings") for c in clients])

    statuses = sorted(r.status_code for r in responses)  # type: ignore[attr-defined]
    assert statuses == [201, 409, 409]
    with scratch_engine.connect() as conn:
        active = conn.execute(text(
            "SELECT count(*) FROM meetings WHERE team_id = 'team_lead' AND ended_at IS NULL"
        )).scalar()  # fmt: skip
    assert active == 1


def test_second_request_waits_for_first_and_returns_its_issue(
    committing_api: Callable[[str], TestClient], scratch_engine: Engine
) -> None:
    """Deterministic version: request A has inserted but not committed when B arrives."""
    factory = sessionmaker(bind=scratch_engine, expire_on_commit=False)
    first = factory()
    measurable = first.get(Measurable, "m1")
    user = first.get(User, "u2")
    assert measurable and user
    issue_a, created_a = make_it_an_issue(first, measurable, WEEK, user, SEED_NOW)
    assert created_a

    result: dict[str, object] = {}

    def second_request() -> None:
        with factory() as db:
            m, u = db.get(Measurable, "m1"), db.get(User, "u3")
            issue_b, created_b = make_it_an_issue(db, m, WEEK, u, SEED_NOW)  # type: ignore[arg-type]
            db.commit()
            result.update(id=issue_b.id, created=created_b)

    thread = threading.Thread(target=second_request)
    thread.start()
    thread.join(timeout=1)
    assert thread.is_alive(), "B should be waiting for A's uncommitted insert"

    first.commit()
    thread.join(timeout=5)
    first.close()

    assert result == {"id": issue_a.id, "created": False}
