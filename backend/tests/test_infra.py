"""Smoke tests for the test infrastructure itself."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_health_endpoint_reaches_database(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_migrations_ran(db: Session) -> None:
    assert db.execute(text("SELECT to_regclass('alembic_version')")).scalar() is not None


# The next two tests run in file order: the second proves the first's writes were rolled back.
def test_isolation_part_1_writes_and_commits(db: Session) -> None:
    db.execute(text("CREATE TABLE isolation_probe (id int)"))
    db.execute(text("INSERT INTO isolation_probe VALUES (1)"))
    db.commit()  # must stay inside the test's outer transaction

    assert db.execute(text("SELECT count(*) FROM isolation_probe")).scalar() == 1


def test_isolation_part_2_sees_nothing(db: Session) -> None:
    assert db.execute(text("SELECT to_regclass('isolation_probe')")).scalar() is None
