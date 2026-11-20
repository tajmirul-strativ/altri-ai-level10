"""Roles and team boundaries are enforced on the server (brief 2.4, 2.7; design.md §5).

Seed: u1 Admin (Leadership only) · u2 Team Member (Leadership + Sales) · u3, u4 Leadership ·
u5 Observer (Leadership) · u6 Sales · u7 Observer (Sales) · u8, u9 Operations.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import ApiFactory

LEAD = "/api/teams/team_lead"

READS = [
    f"{LEAD}",
    f"{LEAD}/scorecard",
    f"{LEAD}/issues",
    f"{LEAD}/issues?status=solved",
    f"{LEAD}/todos",
    f"{LEAD}/rocks",
    f"{LEAD}/meetings/mt1",
    f"{LEAD}/meetings/mt1/summary",
]

WRITES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("PUT", f"{LEAD}/measurables/m1/scores/2026-11-09", {"value": 11}),
    ("DELETE", f"{LEAD}/measurables/m5/scores/2026-11-09", None),
    ("POST", f"{LEAD}/measurables/m1/scores/2026-10-26/issue", None),
    ("POST", f"{LEAD}/issues", {"title": "New problem"}),
    ("PATCH", f"{LEAD}/issues/i1", {"priority": 3}),
    ("POST", f"{LEAD}/issues/i1/solve", {"note": "Done"}),
    ("POST", f"{LEAD}/issues/i1/todos", {"title": "Follow up", "owner_id": "u2"}),
    ("PATCH", f"{LEAD}/todos/t31", {"done": True}),
    ("POST", f"{LEAD}/meetings", None),
]


def call(c: TestClient, method: str, url: str, body: dict[str, Any] | None) -> int:
    return c.request(method, url, json=body).status_code


@pytest.mark.parametrize(
    ("user", "teams"),
    [
        ("u1", ["team_lead", "team_ops", "team_sales"]),  # Admin: every team
        ("u2", ["team_lead", "team_sales"]),
        ("u5", ["team_lead"]),
        ("u7", ["team_sales"]),
    ],
)
def test_team_switcher_lists_accessible_teams(api: ApiFactory, user: str, teams: list[str]) -> None:
    response = api(user).get("/api/teams")

    assert response.status_code == 200
    assert sorted(t["id"] for t in response.json()) == teams


@pytest.mark.parametrize("url", READS)
def test_member_of_another_team_cannot_read(api: ApiFactory, url: str) -> None:
    assert api("u6").get(url).status_code == 403


@pytest.mark.parametrize("user", ["u2", "u1"])
def test_unknown_team_gets_the_same_403(api: ApiFactory, user: str) -> None:
    assert api(user).get("/api/teams/team_nope/scorecard").status_code == 403


@pytest.mark.parametrize("url", READS)
def test_observer_can_read_own_team(api: ApiFactory, url: str) -> None:
    assert api("u5").get(url).status_code == 200


@pytest.mark.parametrize(("method", "url", "body"), WRITES)
def test_observer_cannot_write(
    api: ApiFactory, db: Session, method: str, url: str, body: dict[str, Any] | None
) -> None:
    before = db.execute(text("SELECT count(*) FROM issues")).scalar()

    assert call(api("u5"), method, url, body) == 403
    assert db.execute(text("SELECT count(*) FROM issues")).scalar() == before


@pytest.mark.parametrize(("method", "url", "body"), WRITES)
def test_member_of_another_team_cannot_write(
    api: ApiFactory, method: str, url: str, body: dict[str, Any] | None
) -> None:
    assert call(api("u6"), method, url, body) == 403


@pytest.mark.parametrize(("method", "url", "body"), WRITES)
def test_no_session_is_401(
    api: ApiFactory, method: str, url: str, body: dict[str, Any] | None
) -> None:
    anonymous = api(None)
    assert call(anonymous, method, url, body) == 401
    assert anonymous.get(f"{LEAD}/scorecard").status_code == 401


def test_admin_reads_and_writes_a_team_they_do_not_belong_to(api: ApiFactory) -> None:
    admin = api("u1")

    assert admin.get("/api/teams/team_sales/scorecard").status_code == 200
    assert (
        admin.post("/api/teams/team_sales/issues", json={"title": "Admin issue"}).status_code == 201
    )


@pytest.mark.parametrize(
    ("user", "method", "url", "body"),
    [
        # Issue i8 belongs to Sales; reaching it through Leadership must not work.
        ("u2", "PATCH", f"{LEAD}/issues/i8", {"priority": 1}),
        ("u2", "POST", f"{LEAD}/issues/i8/solve", {"note": "x"}),
        ("u2", "PATCH", "/api/teams/team_sales/issues/i1", {"priority": 1}),
        ("u2", "PATCH", f"{LEAD}/todos/t40", {"done": True}),
        ("u2", "PUT", f"{LEAD}/measurables/m6/scores/2026-11-09", {"value": 1}),
        ("u1", "GET", "/api/teams/team_sales/meetings/mt1", None),
    ],
)
def test_records_are_only_reachable_through_their_own_team(
    api: ApiFactory, user: str, method: str, url: str, body: dict[str, Any] | None
) -> None:
    assert call(api(user), method, url, body) == 404
