"""Rules report: every computed value in brief 2.6, in the starter README's JSON format.

Uses the same rule functions as the API, so the report and the app always agree.
"""

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.company_time import current_week, quarter_of, shown_weeks, today
from app.models import Issue, Measurable, Meeting, Rock, Score, Team, Todo
from app.rules import (
    is_overdue,
    measurable_status,
    order_issues,
    rock_progress,
    rock_status,
    todo_completion,
)
from app.summary import meeting_summary


def iso_utc(instant: datetime) -> str:
    return instant.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rating(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def build_rules_report(db: Session, now: datetime) -> dict[str, Any]:
    teams = db.scalars(select(Team).order_by(Team.id)).all()
    return {
        "now": iso_utc(now),
        "teams": {team.id: _team_report(db, team, now) for team in teams},
    }


def _team_report(db: Session, team: Team, now: datetime) -> dict[str, Any]:
    tz = ZoneInfo(team.company.timezone)
    weeks = shown_weeks(now, tz)
    current = current_week(now, tz)
    day = today(now, tz)

    # Measurable status for every shown week.
    measurables = db.scalars(
        select(Measurable).where(Measurable.team_id == team.id).order_by(Measurable.id)
    ).all()
    scores: dict[str, dict[date, Decimal]] = defaultdict(dict)
    for s in db.scalars(
        select(Score).where(
            Score.measurable_id.in_([m.id for m in measurables]),
            Score.week_start.between(weeks[0], weeks[-1]),
        )
    ):
        scores[s.measurable_id][s.week_start] = s.value
    statuses = {
        m.id: {
            w.isoformat(): measurable_status(m.goal, scores[m.id].get(w), w, current) for w in weeks
        }
        for m in measurables
    }

    # To-Dos.
    todos = db.scalars(select(Todo).where(Todo.team_id == team.id)).all()
    completion = {}
    for w in weeks:
        result = todo_completion(todos, w, now, tz)
        completion[w.isoformat()] = None if result is None else {
            "due": result.due,
            "done": result.done,
            "rate_percent": result.rate_percent,
            "meets_target": result.meets_target,
        }  # fmt: skip
    overdue = sorted(t.id for t in todos if is_overdue(t, day))

    # Rocks of the current quarter.
    rocks = db.scalars(
        select(Rock).where(Rock.team_id == team.id, Rock.quarter == quarter_of(day))
    ).all()
    rock_states = {
        r.id: {
            "status": rock_status(r.status, r.milestones, day),
            "progress_percent": rock_progress(r.status, r.milestones),
        }
        for r in rocks
    }

    # Unsolved Issues in Issue order.
    open_issues = db.scalars(
        select(Issue).where(Issue.team_id == team.id, Issue.solved_at.is_(None))
    ).all()

    # Ended meetings.
    meetings = db.scalars(
        select(Meeting).where(Meeting.team_id == team.id, Meeting.ended_at.is_not(None))
    ).all()
    summaries = {}
    for meeting in meetings:
        s = meeting_summary(db, meeting, tz, now)
        summaries[meeting.id] = {
            "scorecard_week": s.scorecard_week.isoformat(),
            "measurable_status": s.measurable_status,
            "issues_solved": s.issues_solved,
            "todos_created": s.todos_created,
            "attendee_ids": s.attendee_ids,
            "rating": _rating(s.rating),
        }

    return {
        "measurable_status": statuses,
        "todo_completion": completion,
        "overdue_todos": overdue,
        "rocks": rock_states,
        "issue_order": [i.id for i in order_issues(open_issues)],
        "meetings": summaries,
    }
