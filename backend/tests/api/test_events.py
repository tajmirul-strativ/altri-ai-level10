"""Live updates (brief 2.5 "Sync", design.md §7).

A committed change is announced to everyone watching the team within about a second; a
rolled-back change never is. The browser then re-reads what changed.
"""

import asyncio
import json
import queue
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.events import publish
from app.main import app
from app.realtime import Broker
from tests.api.conftest import SCRATCH_URL
from tests.conftest import ApiFactory

LEAD = "/api/teams/team_lead"
DSN = SCRATCH_URL.set(drivername="postgresql").render_as_string(hide_password=False)


# --- broker: Postgres LISTEN -> per-team subscribers ------------------------------------------


def _commit_publish(
    engine: Engine, team_id: str, resources: list[Any], *, rollback: bool = False
) -> None:
    with Session(engine) as db:
        publish(db, team_id, resources)
        db.rollback() if rollback else db.commit()


async def _next(q: asyncio.Queue[dict[str, Any]], timeout: float) -> dict[str, Any] | None:
    try:
        return await asyncio.wait_for(q.get(), timeout)
    except TimeoutError:
        return None


def test_committed_change_reaches_team_subscribers(scratch_engine: Engine) -> None:
    async def scenario() -> tuple[Any, Any]:
        broker = Broker(DSN)
        await broker.start()
        lead, sales = broker.subscribe("team_lead"), broker.subscribe("team_sales")
        await asyncio.to_thread(_commit_publish, scratch_engine, "team_lead", ["issues"])
        got = await _next(lead, 2), await _next(sales, 0.3)
        await broker.stop()
        return got

    lead_msg, sales_msg = asyncio.run(scenario())

    assert lead_msg == {"team_id": "team_lead", "resources": ["issues"]}
    assert sales_msg is None  # other teams hear nothing


def test_rolled_back_change_is_never_announced(scratch_engine: Engine) -> None:
    async def scenario() -> Any:
        broker = Broker(DSN)
        await broker.start()
        q = broker.subscribe("team_lead")
        await asyncio.to_thread(
            _commit_publish, scratch_engine, "team_lead", ["issues"], rollback=True
        )
        got = await _next(q, 0.5)
        await broker.stop()
        return got

    assert asyncio.run(scenario()) is None


def test_unsubscribed_queue_is_dropped(scratch_engine: Engine) -> None:
    async def scenario() -> int:
        broker = Broker(DSN)
        await broker.start()
        q = broker.subscribe("team_lead")
        broker.unsubscribe("team_lead", q)
        count = broker.subscriber_count("team_lead")
        await broker.stop()
        return count

    assert asyncio.run(scenario()) == 0


# --- SSE endpoint ----------------------------------------------------------------------------


def test_events_need_a_session(api: ApiFactory) -> None:
    assert api(None).get(f"{LEAD}/events").status_code == 401


def test_events_of_another_team_are_refused(api: ApiFactory) -> None:
    assert api("u6").get(f"{LEAD}/events").status_code == 403


@pytest.fixture
def live_server(committing_api: Callable[[str], TestClient]) -> Iterator[str]:
    """The real app on a random port (the test client can't read an endless stream)."""
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


class EventReader:
    """Reads SSE events from a stream on a background thread, with timeouts."""

    def __init__(self, base_url: str, user_id: str, path: str) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=10)
        self.client.post("/api/auth/login", json={"user_id": user_id}).raise_for_status()
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, args=(path,), daemon=True)
        self.thread.start()

    def _run(self, path: str) -> None:
        with self.client.stream("GET", path) as response:
            self.headers = response.headers
            event = "message"
            for line in response.iter_lines():
                if self._stop.is_set():
                    return
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    self.events.put((event, json.loads(line.split(":", 1)[1])))

    def next(self, timeout: float = 2) -> tuple[str, Any]:
        return self.events.get(timeout=timeout)

    def close(self) -> None:
        self._stop.set()
        self.client.close()


@pytest.fixture
def watch(live_server: str) -> Iterator[Callable[[str], EventReader]]:
    readers: list[EventReader] = []

    def make(user_id: str) -> EventReader:
        reader = EventReader(live_server, user_id, f"{LEAD}/events")
        readers.append(reader)
        assert reader.next() == ("ready", {})
        return reader

    yield make
    for r in readers:
        r.close()


def test_stream_is_server_sent_events(watch: Callable[[str], EventReader]) -> None:
    reader = watch("u3")

    assert reader.headers["content-type"].startswith("text/event-stream")
    assert reader.headers["cache-control"] == "no-cache"


def test_change_reaches_watcher_within_a_second(
    watch: Callable[[str], EventReader], live_server: str
) -> None:
    reader = watch("u3")
    actor = httpx.Client(base_url=live_server)
    actor.post("/api/auth/login", json={"user_id": "u2"})

    started = time.monotonic()
    assert actor.post(f"{LEAD}/issues", json={"title": "Live"}).status_code == 201
    event, data = reader.next(timeout=1)

    assert (event, data) == ("change", {"resources": ["issues"]})
    assert time.monotonic() - started < 1
    actor.close()


def test_facilitator_advancing_reaches_every_attendee(
    watch: Callable[[str], EventReader], live_server: str
) -> None:
    attendees = [watch("u3"), watch("u5")]  # a teammate and an Observer
    facilitator = httpx.Client(base_url=live_server)
    facilitator.post("/api/auth/login", json={"user_id": "u2"})
    meeting_id = facilitator.post(f"{LEAD}/meetings").json()["id"]
    for reader in attendees:
        assert reader.next() == ("change", {"resources": ["meeting"], "meeting_id": meeting_id})

    facilitator.post(f"{LEAD}/meetings/{meeting_id}/advance", json={"from_section": "scorecard"})

    for reader in attendees:
        assert reader.next() == ("change", {"resources": ["meeting"], "meeting_id": meeting_id})
    facilitator.close()
