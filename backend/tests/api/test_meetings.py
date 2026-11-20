"""Level 10 Meeting (brief 2.5 "Meeting Page", design.md §6-7)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.clock import FrozenClock
from tests.conftest import SEED_NOW, ApiFactory

LEAD = "/api/teams/team_lead"
MEETINGS = f"{LEAD}/meetings"


def start(c: TestClient) -> dict[str, Any]:
    response = c.post(MEETINGS)
    assert response.status_code == 201, response.text
    return response.json()


def advance(c: TestClient, meeting_id: str, from_section: str) -> Any:
    return c.post(f"{MEETINGS}/{meeting_id}/advance", json={"from_section": from_section})


@pytest.fixture
def blake(api: ApiFactory) -> TestClient:
    return api("u2")


# --- start / active --------------------------------------------------------------------------


def test_start_meeting_makes_caller_facilitator(blake: TestClient) -> None:
    state = start(blake)

    assert state["team_id"] == "team_lead"
    assert state["facilitator"] == {"id": "u2", "name": "Blake Brooks"}
    assert state["section"] == "scorecard"
    assert state["started_at"] == "2026-11-11T15:00:00Z"
    assert state["section_started_at"] == "2026-11-11T15:00:00Z"
    assert state["ended_at"] is None
    assert state["server_now"] == "2026-11-11T15:00:00Z"
    assert [a["id"] for a in state["attendees"]] == ["u2"]
    assert state["agenda"] == [
        {"section": "scorecard", "title": "Scorecard", "minutes": 5},
        {"section": "ids", "title": "IDS", "minutes": 60},
        {"section": "conclude", "title": "Conclude", "minutes": 10},
    ]


def test_active_meeting_is_found(blake: TestClient) -> None:
    meeting_id = start(blake)["id"]

    assert blake.get(f"{MEETINGS}/active").json()["id"] == meeting_id


def test_no_active_meeting_is_404(blake: TestClient) -> None:
    assert blake.get(f"{MEETINGS}/active").status_code == 404


def test_one_active_meeting_per_team(api: ApiFactory) -> None:
    meeting_id = start(api("u2"))["id"]

    response = api("u3").post(MEETINGS)

    assert response.status_code == 409
    assert response.json()["meeting_id"] == meeting_id


def test_admin_outside_team_can_start_meeting(api: ApiFactory) -> None:
    response = api("u1").post("/api/teams/team_sales/meetings")

    assert response.status_code == 201
    assert response.json()["facilitator"]["id"] == "u1"


# --- join ------------------------------------------------------------------------------------


def test_teammates_and_observers_join(api: ApiFactory) -> None:
    meeting_id = start(api("u2"))["id"]

    api("u3").post(f"{MEETINGS}/{meeting_id}/join")
    state = api("u5").post(f"{MEETINGS}/{meeting_id}/join").json()

    assert [a["id"] for a in state["attendees"]] == ["u2", "u3", "u5"]
    assert next(a for a in state["attendees"] if a["id"] == "u5")["role"] == "observer"


def test_join_is_idempotent(api: ApiFactory) -> None:
    meeting_id = start(api("u2"))["id"]

    api("u3").post(f"{MEETINGS}/{meeting_id}/join")
    state = api("u3").post(f"{MEETINGS}/{meeting_id}/join").json()

    assert [a["id"] for a in state["attendees"]] == ["u2", "u3"]


def test_joining_an_ended_meeting_is_409(blake: TestClient) -> None:
    assert blake.post(f"{MEETINGS}/mt1/join").status_code == 409


def test_late_join_gets_current_section_and_timer(api: ApiFactory, clock: FrozenClock) -> None:
    facilitator = api("u2")
    meeting_id = start(facilitator)["id"]
    clock.advance(timedelta(minutes=6))
    advance(facilitator, meeting_id, "scorecard")
    clock.advance(timedelta(minutes=3))

    state = api("u4").post(f"{MEETINGS}/{meeting_id}/join").json()

    assert state["section"] == "ids"
    assert state["section_started_at"] == "2026-11-11T15:06:00Z"
    assert state["server_now"] == "2026-11-11T15:09:00Z"


# --- advance / end ---------------------------------------------------------------------------


def test_facilitator_advances_through_agenda(blake: TestClient, clock: FrozenClock) -> None:
    meeting_id = start(blake)["id"]

    clock.advance(timedelta(minutes=7))  # over time: nothing moved on its own
    assert blake.get(f"{MEETINGS}/{meeting_id}").json()["section"] == "scorecard"

    ids = advance(blake, meeting_id, "scorecard")
    assert ids.status_code == 200
    assert ids.json()["section"] == "ids"
    assert ids.json()["section_started_at"] == "2026-11-11T15:07:00Z"

    clock.advance(timedelta(minutes=50))
    assert advance(blake, meeting_id, "ids").json()["section"] == "conclude"


def test_only_facilitator_advances(api: ApiFactory) -> None:
    meeting_id = start(api("u2"))["id"]
    api("u3").post(f"{MEETINGS}/{meeting_id}/join")

    assert advance(api("u3"), meeting_id, "scorecard").status_code == 403


def test_stale_advance_is_409_and_skips_nothing(blake: TestClient) -> None:
    meeting_id = start(blake)["id"]
    advance(blake, meeting_id, "scorecard")

    assert advance(blake, meeting_id, "scorecard").status_code == 409  # double click
    assert blake.get(f"{MEETINGS}/{meeting_id}").json()["section"] == "ids"


def test_conclude_has_no_next_section(blake: TestClient) -> None:
    meeting_id = start(blake)["id"]
    advance(blake, meeting_id, "scorecard")
    advance(blake, meeting_id, "ids")

    assert advance(blake, meeting_id, "conclude").status_code == 409


@pytest.mark.parametrize("body", [{}, {"from_section": "headlines"}])
def test_invalid_advance_is_422(blake: TestClient, body: dict[str, Any]) -> None:
    meeting_id = start(blake)["id"]

    assert blake.post(f"{MEETINGS}/{meeting_id}/advance", json=body).status_code == 422


def test_facilitator_can_end_at_any_time(blake: TestClient, clock: FrozenClock) -> None:
    meeting_id = start(blake)["id"]
    clock.advance(timedelta(minutes=2))

    response = blake.post(f"{MEETINGS}/{meeting_id}/end")

    assert response.status_code == 200
    assert response.json()["ended_at"] == "2026-11-11T15:02:00Z"
    assert blake.get(f"{MEETINGS}/active").status_code == 404
    assert blake.post(f"{MEETINGS}/{meeting_id}/end").status_code == 409


def test_only_facilitator_ends(api: ApiFactory) -> None:
    meeting_id = start(api("u2"))["id"]

    assert api("u3").post(f"{MEETINGS}/{meeting_id}/end").status_code == 403


def test_new_meeting_can_start_after_end(blake: TestClient) -> None:
    meeting_id = start(blake)["id"]
    blake.post(f"{MEETINGS}/{meeting_id}/end")

    assert start(blake)["id"] != meeting_id


# --- rating ----------------------------------------------------------------------------------


@pytest.fixture
def in_conclude(api: ApiFactory) -> str:
    """Leadership meeting run by u2, joined by u3 and Observer u5, now in Conclude."""
    facilitator = api("u2")
    meeting_id = start(facilitator)["id"]
    for user in ("u3", "u5"):
        api(user).post(f"{MEETINGS}/{meeting_id}/join")
    advance(facilitator, meeting_id, "scorecard")
    advance(facilitator, meeting_id, "ids")
    return meeting_id


def rate(c: TestClient, meeting_id: str, rating: Any) -> Any:
    return c.put(f"{MEETINGS}/{meeting_id}/rating", json={"rating": rating})


def test_attendees_rate_and_can_change_their_rating(api: ApiFactory, in_conclude: str) -> None:
    rate(api("u2"), in_conclude, 8)
    rate(api("u3"), in_conclude, 7)
    state = rate(api("u3"), in_conclude, 9).json()

    assert state["ratings"] == [{"user_id": "u2", "rating": 8}, {"user_id": "u3", "rating": 9}]
    assert state["average_rating"] == 8.5


def test_observer_cannot_rate(api: ApiFactory, in_conclude: str) -> None:
    assert rate(api("u5"), in_conclude, 8).status_code == 403


def test_non_attendee_must_join_before_rating(api: ApiFactory, in_conclude: str) -> None:
    assert rate(api("u4"), in_conclude, 8).status_code == 409


def test_rating_only_in_conclude(blake: TestClient) -> None:
    meeting_id = start(blake)["id"]

    assert rate(blake, meeting_id, 8).status_code == 409


@pytest.mark.parametrize("rating", [0, 11, 7.5, "8", None])
def test_rating_must_be_1_to_10(api: ApiFactory, in_conclude: str, rating: Any) -> None:
    assert rate(api("u2"), in_conclude, rating).status_code == 422


def test_no_rating_after_end(api: ApiFactory, in_conclude: str) -> None:
    api("u2").post(f"{MEETINGS}/{in_conclude}/end")

    assert rate(api("u3"), in_conclude, 8).status_code == 409


# --- summary ---------------------------------------------------------------------------------


def test_summary_of_a_finished_meeting(api: ApiFactory, clock: FrozenClock) -> None:
    facilitator = api("u2")
    meeting_id = start(facilitator)["id"]
    api("u5").post(f"{MEETINGS}/{meeting_id}/join")
    clock.advance(timedelta(minutes=5))
    advance(facilitator, meeting_id, "scorecard")
    clock.advance(timedelta(minutes=1))
    facilitator.post(f"{LEAD}/issues/i2/solve", json={"note": "Renewed."})
    todo_id = facilitator.post(
        f"{LEAD}/issues/i2/todos", json={"title": "Send thanks", "owner_id": "u2"}
    ).json()["id"]
    advance(facilitator, meeting_id, "ids")
    rate(facilitator, meeting_id, 9)
    clock.advance(timedelta(minutes=1))
    facilitator.post(f"{MEETINGS}/{meeting_id}/end")

    summary = facilitator.get(f"{MEETINGS}/{meeting_id}/summary").json()

    assert summary == {
        "meeting_id": meeting_id,
        "scorecard_week": "2026-11-02",
        "measurable_status": {
            "m1": "off_track", "m2": "on_track", "m3": "off_track", "m4": "on_track",
            "m5": "off_track",
        },
        "issues_solved": ["i2"],
        "todos_created": [todo_id],
        "attendee_ids": ["u2", "u5"],
        "rating": 9.0,
    }  # fmt: skip


def test_summary_of_seeded_meeting(blake: TestClient) -> None:
    summary = blake.get(f"{MEETINGS}/mt2/summary").json()

    assert summary["scorecard_week"] == "2026-10-26"
    assert summary["issues_solved"] == ["i6"]
    assert summary["todos_created"] == ["t30"]
    assert summary["attendee_ids"] == ["u1", "u2", "u3", "u4", "u5"]
    assert summary["rating"] == 8.3


def test_summary_of_active_meeting_is_409(blake: TestClient) -> None:
    meeting_id = start(blake)["id"]

    assert blake.get(f"{MEETINGS}/{meeting_id}/summary").status_code == 409


def test_unknown_meeting_is_404(blake: TestClient) -> None:
    assert blake.get(f"{MEETINGS}/mt999").status_code == 404


def test_seed_now_is_wednesday_9am_chicago() -> None:
    assert SEED_NOW == datetime(2026, 11, 11, 15, 0, tzinfo=UTC)
