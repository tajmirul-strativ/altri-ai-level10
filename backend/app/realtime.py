"""Live team events: Postgres LISTEN -> in-process broker -> SSE (design.md §7).

Writes call `app.events.publish` inside their transaction, which runs `pg_notify`; Postgres
delivers the notification only when that transaction commits. Each API process keeps one
LISTEN connection (the Broker) and fans every notification out to the SSE streams watching
that team. So any number of API processes stay in sync, and a rolled-back change is never sent.

Events only say *what* changed. Browsers re-read it over REST, which is also exactly how they
recover after a reconnect, so a missed event can't leave a stale screen.
"""

import asyncio
import contextlib
import json
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Annotated, Any

import psycopg
from fastapi import Depends
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.events import CHANNEL

Message = dict[str, Any]


class Broker:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._queues: dict[str, set[asyncio.Queue[Message]]] = defaultdict(set)
        self._conn: psycopg.AsyncConnection[Any] | None = None
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._listen())
        await asyncio.wait_for(self._ready.wait(), timeout=10)

    async def _listen(self) -> None:
        while True:  # reconnect if the LISTEN connection drops
            try:
                async with await psycopg.AsyncConnection.connect(self.dsn, autocommit=True) as conn:
                    self._conn = conn
                    await conn.execute(f"LISTEN {CHANNEL}")
                    self._ready.set()
                    async for notify in conn.notifies():
                        self._dispatch(json.loads(notify.payload))
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - keep listening; browsers re-sync on reconnect
                await asyncio.sleep(1)

    def _dispatch(self, message: Message) -> None:
        for q in list(self._queues.get(message.get("team_id", ""), ())):
            q.put_nowait(message)

    def subscribe(self, team_id: str) -> asyncio.Queue[Message]:
        q: asyncio.Queue[Message] = asyncio.Queue()
        self._queues[team_id].add(q)
        return q

    def unsubscribe(self, team_id: str, q: asyncio.Queue[Message]) -> None:
        self._queues[team_id].discard(q)
        if not self._queues[team_id]:
            del self._queues[team_id]

    def subscriber_count(self, team_id: str) -> int:
        return len(self._queues.get(team_id, ()))

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None


def get_events_dsn() -> str:
    """libpq DSN for the LISTEN connection (tests override this)."""
    url = make_url(get_settings().database_url).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


# One broker per event loop and database (normally exactly one per process).
_brokers: dict[tuple[int, str], Broker] = {}


async def get_broker(dsn: Annotated[str, Depends(get_events_dsn)]) -> Broker:
    key = (id(asyncio.get_running_loop()), dsn)
    broker = _brokers.get(key)
    if broker is None:
        broker = _brokers[key] = Broker(dsn)
    await broker.start()
    return broker


async def stop_brokers() -> None:
    loop_id = id(asyncio.get_running_loop())
    for key in [k for k in _brokers if k[0] == loop_id]:
        await _brokers.pop(key).stop()


def sse(event: str, data: Message) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(', ', ': '))}\n\n"


async def team_stream(
    broker: Broker, team_id: str, is_disconnected: Any, heartbeat: float
) -> AsyncIterator[str]:
    q = broker.subscribe(team_id)
    try:
        yield "retry: 2000\n\n"  # browsers reconnect after 2 s
        yield sse("ready", {})
        while not await is_disconnected():
            try:
                message = await asyncio.wait_for(q.get(), timeout=heartbeat)
            except TimeoutError:
                yield ": heartbeat\n\n"  # keeps proxies from closing an idle stream
                continue
            message.pop("team_id", None)
            yield sse("change", message)
    finally:
        broker.unsubscribe(team_id, q)
