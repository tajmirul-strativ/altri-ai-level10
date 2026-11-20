"""Meeting summary (brief 2.5 "Summary", design.md §3).

Computed from current data: Issues solved and To-Dos created count when their timestamp falls
inside the meeting's [started_at, ended_at] window, for the meeting's team.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.company_time import current_week
from app.models import Issue, Measurable, Meeting, Score, Todo
from app.rules import MeasurableStatus, measurable_status, meeting_rating, scorecard_week


@dataclass(frozen=True)
class MeetingSummary:
    meeting_id: str
    scorecard_week: date
    measurable_status: dict[str, MeasurableStatus]
    issues_solved: list[str]
    todos_created: list[str]
    attendee_ids: list[str]
    rating: Decimal | None


def meeting_summary(db: Session, meeting: Meeting, tz: ZoneInfo, now: datetime) -> MeetingSummary:
    if meeting.ended_at is None:
        raise ValueError(f"meeting {meeting.id} has not ended")
    week = scorecard_week(meeting.started_at, tz)
    window = (meeting.started_at, meeting.ended_at)

    measurables = db.scalars(
        select(Measurable).where(Measurable.team_id == meeting.team_id).order_by(Measurable.id)
    ).all()
    scores = {
        s.measurable_id: s.value
        for s in db.scalars(
            select(Score).where(
                Score.measurable_id.in_([m.id for m in measurables]), Score.week_start == week
            )
        )
    }
    issues_solved = db.scalars(
        select(Issue.id).where(Issue.team_id == meeting.team_id, Issue.solved_at.between(*window))
    ).all()
    todos_created = db.scalars(
        select(Todo.id).where(Todo.team_id == meeting.team_id, Todo.created_at.between(*window))
    ).all()

    return MeetingSummary(
        meeting_id=meeting.id,
        scorecard_week=week,
        measurable_status={
            m.id: measurable_status(m.goal, scores.get(m.id), week, current_week(now, tz))
            for m in measurables
        },
        issues_solved=sorted(issues_solved),
        todos_created=sorted(todos_created),
        attendee_ids=sorted(a.user_id for a in meeting.attendees),
        rating=meeting_rating([r.rating for r in meeting.ratings]),
    )
