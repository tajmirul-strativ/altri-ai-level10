"""Change events for live updates (design.md §7).

`publish` queues a Postgres NOTIFY inside the current transaction, so listeners hear about a
change only once it is committed, and never about a change that was rolled back.
"""

import json
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

CHANNEL = "team_events"
Resource = Literal["scorecard", "issues", "todos", "meeting"]


def publish(db: Session, team_id: str, resources: list[Resource], **extra: Any) -> None:
    payload = json.dumps({"team_id": team_id, "resources": resources, **extra})
    db.execute(
        text("SELECT pg_notify(:channel, :payload)"), {"channel": CHANNEL, "payload": payload}
    )
