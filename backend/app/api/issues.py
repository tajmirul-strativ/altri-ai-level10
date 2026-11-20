from datetime import timedelta
from typing import Literal

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import ReadTeam, TeamContext, WriteTeam, is_member
from app.errors import conflict, invalid, not_found
from app.events import publish
from app.models import Issue, Todo, User
from app.rules import order_issues
from app.schemas import IssueCreate, IssueOut, IssuePriority, IssueSolve, TodoCreate, TodoOut
from app.services.views import issue_out, todo_out

router = APIRouter(prefix="/api/teams/{team_id}/issues", tags=["issues"])

TODO_DUE_DAYS = 7


def _issue(ctx: TeamContext, issue_id: str) -> Issue:
    issue = ctx.db.get(Issue, issue_id, populate_existing=True)
    if issue is None or issue.team_id != ctx.team.id:
        raise not_found("Issue")
    return issue


def _open(issue: Issue) -> Issue:
    if issue.solved_at is not None:
        raise conflict("issue_solved", "This Issue is already solved.")
    return issue


@router.get("", summary="Unsolved Issues in Issue order, or solved ones newest first")
def list_issues(ctx: ReadTeam, status: Literal["open", "solved"] = "open") -> list[IssueOut]:
    query = select(Issue).where(Issue.team_id == ctx.team.id)
    if status == "open":
        issues = order_issues(ctx.db.scalars(query.where(Issue.solved_at.is_(None))).all())
    else:
        issues = list(
            ctx.db.scalars(
                query.where(Issue.solved_at.is_not(None)).order_by(Issue.solved_at.desc(), Issue.id)
            )
        )
    return [issue_out(ctx.db, i) for i in issues]


@router.post("", status_code=201, summary="Create an Issue (owner is the creator)")
def create_issue(ctx: WriteTeam, body: IssueCreate) -> IssueOut:
    issue = Issue(
        team_id=ctx.team.id,
        title=body.title,
        owner_id=ctx.user.id,
        priority=body.priority,
        created_at=ctx.now,
    )
    ctx.db.add(issue)
    ctx.db.flush()
    publish(ctx.db, ctx.team.id, ["issues"])
    ctx.db.commit()
    return issue_out(ctx.db, issue)


@router.patch("/{issue_id}", summary="Set or clear an Issue's priority")
def set_priority(ctx: WriteTeam, issue_id: str, body: IssuePriority) -> IssueOut:
    issue = _open(_issue(ctx, issue_id))
    issue.priority = body.priority
    publish(ctx.db, ctx.team.id, ["issues"])
    ctx.db.commit()
    return issue_out(ctx.db, issue)


@router.post("/{issue_id}/solve", summary="Solve an Issue with a note")
def solve_issue(ctx: WriteTeam, issue_id: str, body: IssueSolve) -> IssueOut:
    issue = _open(_issue(ctx, issue_id))
    issue.solved_at = ctx.now
    issue.resolution_note = body.note
    publish(ctx.db, ctx.team.id, ["issues", "scorecard"])
    ctx.db.commit()
    return issue_out(ctx.db, issue)


@router.post("/{issue_id}/todos", status_code=201, summary="Add a To-Do linked to the Issue")
def add_todo(ctx: WriteTeam, issue_id: str, body: TodoCreate) -> TodoOut:
    issue = _issue(ctx, issue_id)
    owner = ctx.db.get(User, body.owner_id)
    if owner is None or owner.role == "observer" or not is_member(ctx.db, ctx.team.id, owner.id):
        raise invalid("The owner must be one of this team's Admins or Team Members.")
    todo = Todo(
        team_id=ctx.team.id,
        title=body.title,
        owner_id=owner.id,
        due_date=ctx.today + timedelta(days=TODO_DUE_DAYS),
        source_issue_id=issue.id,
        created_at=ctx.now,
    )
    ctx.db.add(todo)
    ctx.db.flush()
    publish(ctx.db, ctx.team.id, ["todos"])
    ctx.db.commit()
    return todo_out(ctx.db, todo, ctx.today)
