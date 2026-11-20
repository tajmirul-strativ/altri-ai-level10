"""Scorecard section (brief 2.5): 13 weeks, inline score edits, Make it an Issue."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.clock import FrozenClock
from tests.conftest import ApiFactory

LEAD = "/api/teams/team_lead"


def cell(scorecard: dict[str, Any], measurable_id: str, week: str) -> dict[str, Any]:
    row = next(m for m in scorecard["measurables"] if m["id"] == measurable_id)
    return next(c for c in row["cells"] if c["week_start"] == week)


@pytest.fixture
def blake(api: ApiFactory) -> TestClient:
    return api("u2")


def test_scorecard_shows_13_weeks_ending_with_current(blake: TestClient) -> None:
    body = blake.get(f"{LEAD}/scorecard").json()

    assert body["current_week"] == "2026-11-09"
    assert body["last_closed_week"] == "2026-11-02"
    assert body["weeks"][0] == "2026-08-17"
    assert body["weeks"][-1] == "2026-11-09"
    assert len(body["weeks"]) == 13
    assert [m["id"] for m in body["measurables"]] == ["m1", "m2", "m3", "m4", "m5"]


def test_measurable_row_has_name_owner_goal_unit(blake: TestClient) -> None:
    body = blake.get(f"{LEAD}/scorecard").json()
    m3 = next(m for m in body["measurables"] if m["id"] == "m3")

    assert m3["name"] == "Avg first response"
    assert m3["unit"] == "hours"
    assert m3["owner"] == {"id": "u4", "name": "Dana Diaz"}
    assert m3["goal"] == {"type": "between", "value": None, "min": 2, "max": 4}
    assert len(m3["cells"]) == 13


@pytest.mark.parametrize(
    ("measurable_id", "week", "value", "status"),
    [
        ("m1", "2026-11-02", 8, "off_track"),
        ("m2", "2026-11-02", 3.0, "on_track"),  # boundary
        ("m5", "2026-11-02", None, "off_track"),  # closed week, no score
        ("m5", "2026-11-09", 520, "on_track"),
        ("m1", "2026-11-09", None, "pending"),  # current week, no score
    ],
)
def test_cells_have_value_and_status(
    blake: TestClient, measurable_id: str, week: str, value: float | None, status: str
) -> None:
    c = cell(blake.get(f"{LEAD}/scorecard").json(), measurable_id, week)

    assert c["value"] == value
    assert c["status"] == status


def test_cell_shows_its_open_issue(blake: TestClient) -> None:
    body = blake.get(f"{LEAD}/scorecard").json()

    assert cell(body, "m1", "2026-11-02")["open_issue_id"] == "i5"
    assert cell(body, "m4", "2026-10-26")["open_issue_id"] is None  # i6 is solved


# --- editing scores ------------------------------------------------------------------------


def test_edit_current_week_score(blake: TestClient) -> None:
    response = blake.put(f"{LEAD}/measurables/m1/scores/2026-11-09", json={"value": 11})

    assert response.status_code == 200
    assert response.json()["value"] == 11
    assert response.json()["status"] == "on_track"
    assert cell(blake.get(f"{LEAD}/scorecard").json(), "m1", "2026-11-09")["value"] == 11


def test_edit_last_closed_week_score(blake: TestClient) -> None:
    response = blake.put(f"{LEAD}/measurables/m5/scores/2026-11-02", json={"value": 500})

    assert response.status_code == 200
    assert response.json()["status"] == "on_track"  # boundary: at least 500


def test_last_save_wins(api: ApiFactory) -> None:
    api("u2").put(f"{LEAD}/measurables/m2/scores/2026-11-09", json={"value": 2.5})
    api("u3").put(f"{LEAD}/measurables/m2/scores/2026-11-09", json={"value": 3.4})

    c = cell(api("u4").get(f"{LEAD}/scorecard").json(), "m2", "2026-11-09")
    assert (c["value"], c["status"]) == (3.4, "off_track")


def test_decimal_scores_are_kept_exactly(blake: TestClient) -> None:
    blake.put(f"{LEAD}/measurables/m2/scores/2026-11-09", json={"value": 3.1})

    assert cell(blake.get(f"{LEAD}/scorecard").json(), "m2", "2026-11-09")["value"] == 3.1


@pytest.mark.parametrize(
    ("week", "body"),
    [
        ("2026-08-10", {"value": 1}),  # older than the 13 shown weeks
        ("2026-11-16", {"value": 1}),  # future week
        ("2026-11-10", {"value": 1}),  # not a Monday
        ("not-a-date", {"value": 1}),
        ("2026-11-09", {"value": "abc"}),
        ("2026-11-09", {}),
        ("2026-11-09", {"value": 1, "extra": True}),
    ],
)
def test_invalid_score_edits_are_422(blake: TestClient, week: str, body: dict[str, Any]) -> None:
    assert blake.put(f"{LEAD}/measurables/m1/scores/{week}", json=body).status_code == 422


def test_unknown_measurable_is_404(blake: TestClient) -> None:
    response = blake.put(f"{LEAD}/measurables/m99/scores/2026-11-09", json={"value": 1})

    assert response.status_code == 404


def test_clear_a_score(blake: TestClient) -> None:
    assert blake.delete(f"{LEAD}/measurables/m5/scores/2026-11-09").status_code == 204

    assert cell(blake.get(f"{LEAD}/scorecard").json(), "m5", "2026-11-09")["status"] == "pending"


# --- Make it an Issue ------------------------------------------------------------------------


def test_make_it_an_issue_creates_issue_owned_by_clicker(api: ApiFactory) -> None:
    response = api("u3").post(f"{LEAD}/measurables/m1/scores/2026-10-26/issue")

    assert response.status_code == 201
    issue = response.json()
    assert issue["title"] == "New deals closed, week of Oct 26"
    assert issue["owner"]["id"] == "u3"
    assert issue["priority"] is None
    assert issue["created_at"] == "2026-11-11T15:00:00Z"
    assert issue["source"] == {
        "measurable_id": "m1",
        "measurable_name": "New deals closed",
        "week_start": "2026-10-26",
    }


def test_make_it_an_issue_twice_returns_the_same_issue(api: ApiFactory) -> None:
    first = api("u3").post(f"{LEAD}/measurables/m1/scores/2026-10-26/issue")
    second = api("u4").post(f"{LEAD}/measurables/m1/scores/2026-10-26/issue")

    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["owner"]["id"] == "u3"  # unchanged


def test_make_it_an_issue_returns_existing_seeded_issue(blake: TestClient) -> None:
    response = blake.post(f"{LEAD}/measurables/m1/scores/2026-11-02/issue")

    assert response.status_code == 200
    assert response.json()["id"] == "i5"


def test_solved_issue_does_not_block_a_new_one(blake: TestClient) -> None:
    # i6 (Payroll runs, week of Oct 26) is solved.
    response = blake.post(f"{LEAD}/measurables/m4/scores/2026-10-26/issue")

    assert response.status_code == 201
    assert response.json()["id"] != "i6"


@pytest.mark.parametrize(
    "path",
    [
        "m2/scores/2026-11-02",  # on track
        "m1/scores/2026-11-09",  # pending (current week, no score)
    ],
)
def test_make_it_an_issue_on_a_cell_that_is_not_off_track_is_409(
    blake: TestClient, path: str
) -> None:
    assert blake.post(f"{LEAD}/measurables/{path}/issue").status_code == 409


def test_admin_outside_team_can_make_it_an_issue(api: ApiFactory) -> None:
    response = api("u1").post("/api/teams/team_sales/measurables/m6/scores/2026-11-02/issue")

    assert response.status_code == 201
    assert response.json()["owner"]["id"] == "u1"


def test_week_boundary_follows_company_time(blake: TestClient, clock: FrozenClock) -> None:
    # Sun Nov 15 23:59 CST: week of Nov 9 is still current, so its empty cells are pending.
    clock.set(datetime(2026, 11, 16, 5, 59, tzinfo=UTC))
    assert blake.get(f"{LEAD}/scorecard").json()["current_week"] == "2026-11-09"

    # Mon Nov 16 00:00 CST: week of Nov 9 closed; its empty cells are now off track.
    clock.set(datetime(2026, 11, 16, 6, 0, tzinfo=UTC))
    body = blake.get(f"{LEAD}/scorecard").json()
    assert body["current_week"] == "2026-11-16"
    assert cell(body, "m1", "2026-11-09")["status"] == "off_track"
