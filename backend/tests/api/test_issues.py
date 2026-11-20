"""Issues section (brief 2.5): list in Issue order, create, set priority, solve, add To-Do."""

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


def open_ids(c: TestClient) -> list[str]:
    return [i["id"] for i in c.get(f"{LEAD}/issues").json()]


def test_open_issues_in_issue_order(blake: TestClient) -> None:
    assert open_ids(blake) == ["i2", "i1", "i5", "i3", "i4"]


def test_open_issue_fields(blake: TestClient) -> None:
    i5 = next(i for i in blake.get(f"{LEAD}/issues").json() if i["id"] == "i5")

    assert i5 == {
        "id": "i5",
        "title": "New deals closed, week of Nov 2",
        "owner": {"id": "u2", "name": "Blake Brooks"},
        "priority": 4,
        "created_at": "2026-11-09T16:00:00Z",
        "solved_at": None,
        "resolution_note": None,
        "source": {
            "measurable_id": "m1",
            "measurable_name": "New deals closed",
            "week_start": "2026-11-02",
        },
    }


def test_solved_issues_newest_first_with_time_and_note(blake: TestClient) -> None:
    solved = blake.get(f"{LEAD}/issues?status=solved").json()

    assert [i["id"] for i in solved] == ["i6", "i7"]
    assert solved[0]["solved_at"] == "2026-11-04T15:40:00Z"
    assert solved[0]["resolution_note"] == "Bank holiday moved the run; added a reminder."


def test_unknown_status_filter_is_422(blake: TestClient) -> None:
    assert blake.get(f"{LEAD}/issues?status=all").status_code == 422


# --- create ----------------------------------------------------------------------------------


def test_create_issue_owner_is_creator(api: ApiFactory) -> None:
    response = api("u3").post(f"{LEAD}/issues", json={"title": "  Office lease renewal  "})

    assert response.status_code == 201
    issue = response.json()
    assert issue["title"] == "Office lease renewal"
    assert issue["owner"]["id"] == "u3"
    assert issue["priority"] is None
    assert issue["created_at"] == "2026-11-11T15:00:00Z"
    assert issue["source"] is None


def test_new_issue_without_priority_goes_last(blake: TestClient) -> None:
    new_id = blake.post(f"{LEAD}/issues", json={"title": "Newest"}).json()["id"]

    assert open_ids(blake)[-1] == new_id


def test_new_issue_with_priority_5_goes_after_older_5s(blake: TestClient) -> None:
    new_id = blake.post(f"{LEAD}/issues", json={"title": "Urgent", "priority": 5}).json()["id"]

    assert open_ids(blake)[:3] == ["i2", "i1", new_id]


@pytest.mark.parametrize(
    "body",
    [
        {"title": ""},
        {"title": "   "},
        {},
        {"title": "x", "priority": 0},
        {"title": "x", "priority": 6},
        {"title": "x", "priority": "high"},
        {"title": "x" * 201},
        {"title": "x", "owner_id": "u1"},  # owner is always the creator
    ],
)
def test_invalid_new_issue_is_422(blake: TestClient, body: dict[str, Any]) -> None:
    assert blake.post(f"{LEAD}/issues", json=body).status_code == 422


# --- priority --------------------------------------------------------------------------------


def test_set_priority_reorders(blake: TestClient) -> None:
    response = blake.patch(f"{LEAD}/issues/i3", json={"priority": 5})

    assert response.status_code == 200
    assert response.json()["priority"] == 5
    assert open_ids(blake) == ["i3", "i2", "i1", "i5", "i4"]  # i3 is the oldest 5


def test_clear_priority_moves_issue_last(blake: TestClient) -> None:
    blake.patch(f"{LEAD}/issues/i2", json={"priority": None})

    assert open_ids(blake) == ["i1", "i5", "i3", "i4", "i2"]  # among no-priority, i4 is older


@pytest.mark.parametrize("body", [{"priority": 0}, {"priority": 6}, {}, {"title": "x"}])
def test_invalid_priority_is_422(blake: TestClient, body: dict[str, Any]) -> None:
    assert blake.patch(f"{LEAD}/issues/i1", json=body).status_code == 422


def test_cannot_change_priority_of_solved_issue(blake: TestClient) -> None:
    assert blake.patch(f"{LEAD}/issues/i6", json={"priority": 5}).status_code == 409


def test_unknown_issue_is_404(blake: TestClient) -> None:
    assert blake.patch(f"{LEAD}/issues/i999", json={"priority": 1}).status_code == 404


# --- solve -----------------------------------------------------------------------------------


def test_solve_with_note(blake: TestClient, clock: FrozenClock) -> None:
    clock.set(datetime(2026, 11, 11, 15, 30, tzinfo=UTC))

    response = blake.post(f"{LEAD}/issues/i2/solve", json={"note": "Both accounts renewed."})

    assert response.status_code == 200
    assert response.json()["solved_at"] == "2026-11-11T15:30:00Z"
    assert response.json()["resolution_note"] == "Both accounts renewed."
    assert "i2" not in open_ids(blake)
    assert blake.get(f"{LEAD}/issues?status=solved").json()[0]["id"] == "i2"


@pytest.mark.parametrize("body", [{"note": ""}, {"note": "   "}, {}])
def test_solve_needs_a_note(blake: TestClient, body: dict[str, Any]) -> None:
    assert blake.post(f"{LEAD}/issues/i2/solve", json=body).status_code == 422


def test_solving_twice_is_409(blake: TestClient) -> None:
    assert blake.post(f"{LEAD}/issues/i6/solve", json={"note": "again"}).status_code == 409


# --- add a To-Do -----------------------------------------------------------------------------


def test_add_todo_to_issue(blake: TestClient) -> None:
    response = blake.post(
        f"{LEAD}/issues/i2/todos", json={"title": "Call account C", "owner_id": "u4"}
    )

    assert response.status_code == 201
    todo = response.json()
    assert todo["title"] == "Call account C"
    assert todo["owner"] == {"id": "u4", "name": "Dana Diaz"}
    assert todo["due_date"] == "2026-11-18"  # 7 days after today (Nov 11)
    assert todo["source_issue"] == {"id": "i2", "title": "Two key accounts at risk"}
    assert todo["created_at"] == "2026-11-11T15:00:00Z"
    assert todo["done_at"] is None


def test_todo_due_date_uses_company_today(blake: TestClient, clock: FrozenClock) -> None:
    clock.set(datetime(2026, 11, 11, 5, 30, tzinfo=UTC))  # still Nov 10 in Chicago

    todo = blake.post(f"{LEAD}/issues/i2/todos", json={"title": "x", "owner_id": "u2"}).json()

    assert todo["due_date"] == "2026-11-17"


def test_admin_member_can_own_todo(blake: TestClient) -> None:
    response = blake.post(f"{LEAD}/issues/i2/todos", json={"title": "x", "owner_id": "u1"})

    assert response.status_code == 201


@pytest.mark.parametrize(
    ("team", "issue", "owner"),
    [
        ("team_lead", "i2", "u5"),  # Observer
        ("team_lead", "i2", "u6"),  # member of another team
        ("team_lead", "i2", "u99"),  # unknown user
        ("team_sales", "i8", "u1"),  # Admin who isn't a Sales member (agreed rule)
    ],
)
def test_todo_owner_must_be_team_admin_or_member(
    api: ApiFactory, team: str, issue: str, owner: str
) -> None:
    response = api("u2").post(
        f"/api/teams/{team}/issues/{issue}/todos", json={"title": "x", "owner_id": owner}
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body", [{"title": "", "owner_id": "u2"}, {"owner_id": "u2"}, {"title": "x"}]
)
def test_invalid_todo_is_422(blake: TestClient, body: dict[str, Any]) -> None:
    assert blake.post(f"{LEAD}/issues/i2/todos", json=body).status_code == 422
