"""Turn ORM rows into response bodies."""

from datetime import date

from sqlalchemy.orm import Session

from app.models import Issue, Measurable, Meeting, Todo, User
from app.rules import is_overdue, meeting_rating
from app.schemas import (
    AgendaItem,
    IssueOut,
    IssueRef,
    IssueSource,
    MeetingOut,
    RatingOut,
    TodoOut,
    UserOption,
    UserRef,
)

AGENDA = [
    AgendaItem(section="scorecard", title="Scorecard", minutes=5),
    AgendaItem(section="ids", title="IDS", minutes=60),
    AgendaItem(section="conclude", title="Conclude", minutes=10),
]


def user_ref(db: Session, user_id: str) -> UserRef:
    user = db.get(User, user_id)
    assert user is not None
    return UserRef(id=user.id, name=user.name)


def issue_out(db: Session, issue: Issue) -> IssueOut:
    source = None
    if issue.source_measurable_id and issue.source_week_start:
        measurable = db.get(Measurable, issue.source_measurable_id)
        assert measurable is not None
        source = IssueSource(
            measurable_id=measurable.id,
            measurable_name=measurable.name,
            week_start=issue.source_week_start,
        )
    return IssueOut(
        id=issue.id,
        title=issue.title,
        owner=user_ref(db, issue.owner_id),
        priority=issue.priority,
        created_at=issue.created_at,
        solved_at=issue.solved_at,
        resolution_note=issue.resolution_note,
        source=source,
    )


def todo_out(db: Session, todo: Todo, today: date) -> TodoOut:
    source = db.get(Issue, todo.source_issue_id) if todo.source_issue_id else None
    return TodoOut(
        id=todo.id,
        title=todo.title,
        owner=user_ref(db, todo.owner_id),
        due_date=todo.due_date,
        done_at=todo.done_at,
        overdue=is_overdue(todo, today),
        source_issue=IssueRef(id=source.id, title=source.title) if source else None,
        created_at=todo.created_at,
    )


def meeting_out(db: Session, meeting: Meeting, now) -> MeetingOut:  # noqa: ANN001
    db.refresh(meeting, ["attendees", "ratings"])
    attendees = [db.get(User, a.user_id) for a in meeting.attendees]
    rating = meeting_rating([r.rating for r in meeting.ratings])
    return MeetingOut(
        id=meeting.id,
        team_id=meeting.team_id,
        facilitator=user_ref(db, meeting.facilitator_id),
        started_at=meeting.started_at,
        ended_at=meeting.ended_at,
        section=meeting.section,  # type: ignore[arg-type]
        section_started_at=meeting.section_started_at,
        server_now=now,
        agenda=AGENDA,
        attendees=[UserOption(id=u.id, name=u.name, role=u.role) for u in attendees if u],
        ratings=[RatingOut(user_id=r.user_id, rating=r.rating) for r in meeting.ratings],
        average_rating=float(rating) if rating is not None else None,
    )
