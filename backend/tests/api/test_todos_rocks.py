"""To-Dos and Rocks sections (brief 2.5)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.clock import FrozenClock
from tests.conftest import ApiFactory

LEAD = "/api/teams/team_lead"


@pytest.fixture
def blake(api: ApiFactory) -> TestClient:
    return api("u2")


def todo(c: TestClient, todo_id: str, team: str = "team_lead") -> dict[str, Any]:
    return next(t for t in c.get(f"/api/teams/{team}/todos").json()["todos"] if t["id"] == todo_id)


def test_todos_have_owner_due_done_source_and_overdue_flag(blake: TestClient) -> None:
    body = blake.get(f"{LEAD}/todos").json()
    by_id = {t["id"]: t for t in body["todos"]}

    assert len(by_id) == 18
    assert by_id["t20"]["source_issue"] == {"id": "i7", "title": "Onboarding docs are outdated"}
    assert by_id["t20"]["done_at"] == "2026-11-03T20:00:00Z"
    assert by_id["t12"]["owner"] == {"id": "u3", "name": "Casey Cho"}
    assert sorted(i for i, t in by_id.items() if t["overdue"]) == ["t12", "t31"]


def test_todos_are_listed_by_due_date(blake: TestClient) -> None:
    dates = [t["due_date"] for t in blake.get(f"{LEAD}/todos").json()["todos"]]

    assert dates == sorted(dates)


def test_last_closed_week_completion_rate(blake: TestClient) -> None:
    body = blake.get(f"{LEAD}/todos").json()

    assert body["last_closed_week"] == {
        "week_start": "2026-11-02",
        "completion": {"due": 10, "done": 9, "rate_percent": 90, "meets_target": True},
    }


def test_last_closed_week_with_nothing_due_has_no_rate(api: ApiFactory) -> None:
    body = api("u6").get("/api/teams/team_sales/todos").json()

    assert body["last_closed_week"] == {"week_start": "2026-11-02", "completion": None}


def test_mark_done_and_undo(blake: TestClient, clock: FrozenClock) -> None:
    clock.set(datetime(2026, 11, 11, 16, 0, tzinfo=UTC))

    done = blake.patch(f"{LEAD}/todos/t31", json={"done": True})
    assert done.status_code == 200
    assert done.json()["done_at"] == "2026-11-11T16:00:00Z"
    assert done.json()["overdue"] is False

    undone = blake.patch(f"{LEAD}/todos/t31", json={"done": False})
    assert undone.json()["done_at"] is None
    assert undone.json()["overdue"] is True


def test_marking_done_twice_keeps_first_done_time(blake: TestClient, clock: FrozenClock) -> None:
    blake.patch(f"{LEAD}/todos/t31", json={"done": True})
    clock.set(datetime(2026, 11, 12, 15, 0, tzinfo=UTC))
    blake.patch(f"{LEAD}/todos/t31", json={"done": True})

    assert todo(blake, "t31")["done_at"] == "2026-11-11T15:00:00Z"


@pytest.mark.parametrize("body", [{}, {"done": "yes"}, {"done": True, "title": "x"}])
def test_invalid_todo_update_is_422(blake: TestClient, body: dict[str, Any]) -> None:
    assert blake.patch(f"{LEAD}/todos/t31", json=body).status_code == 422


def test_unknown_todo_is_404(blake: TestClient) -> None:
    assert blake.patch(f"{LEAD}/todos/t999", json={"done": True}).status_code == 404


# --- Rocks -----------------------------------------------------------------------------------


def test_rocks_with_computed_status_and_progress(blake: TestClient) -> None:
    rocks = {r["id"]: r for r in blake.get(f"{LEAD}/rocks").json()}

    summary = {k: (r["status"], r["progress_percent"]) for k, r in rocks.items()}
    assert summary == {
        "r1": ("on_track", 33),
        "r2": ("off_track", 13),
        "r3": ("complete", 100),
        "r4": ("off_track", 0),
        "r5": ("on_track", 0),
    }
    assert rocks["r2"]["owner"] == {"id": "u3", "name": "Casey Cho"}
    assert rocks["r2"]["title"] == "Hire VP of Sales"


def test_rock_milestones_in_due_order_with_past_due_flag(blake: TestClient) -> None:
    r1 = next(r for r in blake.get(f"{LEAD}/rocks").json() if r["id"] == "r1")
    r2 = next(r for r in blake.get(f"{LEAD}/rocks").json() if r["id"] == "r2")

    assert [m["id"] for m in r1["milestones"]] == ["ms1", "ms2", "ms3"]
    assert r1["milestones"][1] == {
        "id": "ms2", "title": "Portal beta", "due_date": "2026-11-11", "done": False,
        "past_due": False,  # due today
    }  # fmt: skip
    assert next(m for m in r2["milestones"] if m["id"] == "ms5")["past_due"] is True


def test_rocks_are_read_only(blake: TestClient) -> None:
    assert blake.patch(f"{LEAD}/rocks", json={}).status_code == 405
