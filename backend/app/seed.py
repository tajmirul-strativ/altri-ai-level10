"""Load seed.json (brief 2.7). Safe to rerun.

- `load_seed` inserts every seed record that isn't there yet and never overwrites existing
  rows, so rerunning it keeps whatever users changed or created.
- `reset_database` empties every table and loads the seed again: a freshly seeded database,
  which is what the rules report is defined against.

Seed ids are kept as-is (`u1`, `t12`). Afterwards the id sequences are moved past the highest
seeded number, so new rows continue the same style (`i10`, `t42`, `mt3`).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Table, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Company,
    Issue,
    Measurable,
    Meeting,
    MeetingAttendee,
    MeetingRating,
    Milestone,
    Rock,
    Score,
    Team,
    TeamMembership,
    Todo,
    User,
)

ALL_TABLES = (
    "meeting_ratings", "meeting_attendees", "meetings", "todos", "issues", "milestones",
    "rocks", "scores", "measurables", "team_memberships", "teams", "users", "companies",
)  # fmt: skip

# sequence name -> (table, id prefix)
ID_SEQUENCES = {
    "issues_id_seq": ("issues", "i"),
    "todos_id_seq": ("todos", "t"),
    "meetings_id_seq": ("meetings", "mt"),
}


def read_seed(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or get_settings().seed_path).read_text())


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _insert_missing(db: Session, table: Table, rows: list[dict[str, Any]]) -> None:
    if rows:
        db.execute(insert(table).values(rows).on_conflict_do_nothing())


def load_seed(db: Session, data: dict[str, Any]) -> None:
    """Insert every seed record that doesn't exist yet. Does not commit."""
    company = data["company"]
    plan: list[tuple[Table, list[dict[str, Any]]]] = [
        (Company.__table__, [dict(id=company["id"], name=company["name"],
                                  timezone=company["timezone"])]),
        (User.__table__, [dict(id=u["id"], company_id=company["id"], name=u["name"],
                               email=u["email"], role=u["role"]) for u in data["users"]]),
        (Team.__table__, [dict(id=t["id"], company_id=company["id"], name=t["name"])
                          for t in data["teams"]]),
        (TeamMembership.__table__, [dict(team_id=m["team_id"], user_id=m["user_id"])
                                    for m in data["memberships"]]),
        (Measurable.__table__, [
            dict(id=m["id"], team_id=m["team_id"], name=m["name"], owner_id=m["owner_id"],
                 unit=m["unit"], goal_type=m["goal"]["type"], goal_value=m["goal"].get("value"),
                 goal_min=m["goal"].get("min"), goal_max=m["goal"].get("max"))
            for m in data["measurables"]]),
        (Score.__table__, [dict(measurable_id=s["measurable_id"], week_start=s["week_start"],
                                value=str(s["value"])) for s in data["scores"]]),
        (Rock.__table__, [dict(id=r["id"], team_id=r["team_id"], title=r["title"],
                               owner_id=r["owner_id"], quarter=r["quarter"], status=r["status"])
                          for r in data["rocks"]]),
        (Milestone.__table__, [dict(id=m["id"], rock_id=m["rock_id"], title=m["title"],
                                    due_date=m["due_date"], done=m["done"])
                               for m in data["milestones"]]),
        (Issue.__table__, [
            dict(id=i["id"], team_id=i["team_id"], title=i["title"], owner_id=i["owner_id"],
                 priority=i["priority"], created_at=_ts(i["created_at"]),
                 solved_at=_ts(i["solved_at"]), resolution_note=i["resolution_note"],
                 source_measurable_id=(i["source"] or {}).get("measurable_id"),
                 source_week_start=(i["source"] or {}).get("week_start"))
            for i in data["issues"]]),
        (Todo.__table__, [
            dict(id=t["id"], team_id=t["team_id"], title=t["title"], owner_id=t["owner_id"],
                 due_date=t["due_date"], done_at=_ts(t["done_at"]),
                 source_issue_id=t["source_issue_id"], created_at=_ts(t["created_at"]))
            for t in data["todos"]]),
        # Seeded meetings have ended; they sit in the last section.
        (Meeting.__table__, [
            dict(id=m["id"], team_id=m["team_id"], facilitator_id=m["facilitator_id"],
                 started_at=_ts(m["started_at"]), ended_at=_ts(m["ended_at"]),
                 section="conclude", section_started_at=_ts(m["started_at"]))
            for m in data["meetings"]]),
        (MeetingAttendee.__table__, [dict(meeting_id=m["id"], user_id=u,
                                          joined_at=_ts(m["started_at"]))
                                     for m in data["meetings"] for u in m["attendee_ids"]]),
        (MeetingRating.__table__, [dict(meeting_id=m["id"], user_id=r["user_id"],
                                        rating=r["rating"])
                                   for m in data["meetings"] for r in m["ratings"]]),
    ]  # fmt: skip
    for table, rows in plan:
        _insert_missing(db, table, rows)
    _advance_id_sequences(db)
    db.flush()


def _advance_id_sequences(db: Session) -> None:
    """Make each id sequence continue after the highest numeric id with its prefix."""
    for sequence, (table, prefix) in ID_SEQUENCES.items():
        highest = db.execute(
            text(f"SELECT max(substring(id FROM :pattern)::int) FROM {table} WHERE id ~ :match"),
            {"pattern": f"^{prefix}([0-9]+)$", "match": f"^{prefix}[0-9]+$"},
        ).scalar()
        if highest:
            db.execute(text("SELECT setval(:seq, :value, true)"),
                       {"seq": sequence, "value": highest})  # fmt: skip
        else:
            db.execute(text("SELECT setval(:seq, 1, false)"), {"seq": sequence})


def reset_database(db: Session, data: dict[str, Any]) -> None:
    """Empty every table and load the seed again. Does not commit."""
    db.execute(text(f"TRUNCATE {', '.join(ALL_TABLES)} RESTART IDENTITY CASCADE"))
    load_seed(db, data)
