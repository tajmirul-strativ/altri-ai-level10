from fastapi import APIRouter
from sqlalchemy import select

from app.company_time import quarter_of
from app.deps import ReadTeam, WriteTeam
from app.errors import not_found
from app.events import publish
from app.models import Rock, Todo
from app.rules import rock_progress, rock_status, todo_completion
from app.schemas import (
    CompletionOut,
    MilestoneOut,
    RockOut,
    TodoOut,
    TodosOut,
    TodoUpdate,
    WeekCompletion,
)
from app.services.views import todo_out, user_ref

router = APIRouter(prefix="/api/teams/{team_id}", tags=["todos", "rocks"])


@router.get("/todos", summary="To-Dos by due date, plus last closed week's completion rate")
def list_todos(ctx: ReadTeam) -> TodosOut:
    todos = ctx.db.scalars(
        select(Todo).where(Todo.team_id == ctx.team.id).order_by(Todo.due_date, Todo.id)
    ).all()
    week = ctx.last_closed_week
    completion = todo_completion(todos, week, ctx.now, ctx.tz)
    return TodosOut(
        todos=[todo_out(ctx.db, t, ctx.today) for t in todos],
        last_closed_week=WeekCompletion(
            week_start=week,
            completion=CompletionOut(**completion.__dict__) if completion else None,
        ),
    )


@router.patch("/todos/{todo_id}", summary="Mark a To-Do done, or undo")
def update_todo(ctx: WriteTeam, todo_id: str, body: TodoUpdate) -> TodoOut:
    todo = ctx.db.get(Todo, todo_id, populate_existing=True)
    if todo is None or todo.team_id != ctx.team.id:
        raise not_found("To-Do")
    if body.done and todo.done_at is None:
        todo.done_at = ctx.now
    elif not body.done:
        todo.done_at = None
    publish(ctx.db, ctx.team.id, ["todos"])
    ctx.db.commit()
    return todo_out(ctx.db, todo, ctx.today)


@router.get("/rocks", summary="Current quarter's Rocks with status, progress and Milestones")
def list_rocks(ctx: ReadTeam) -> list[RockOut]:
    rocks = ctx.db.scalars(
        select(Rock)
        .where(Rock.team_id == ctx.team.id, Rock.quarter == quarter_of(ctx.today))
        .order_by(Rock.id)
    ).all()
    return [
        RockOut(
            id=r.id,
            title=r.title,
            owner=user_ref(ctx.db, r.owner_id),
            quarter=r.quarter,
            status=rock_status(r.status, r.milestones, ctx.today),
            progress_percent=rock_progress(r.status, r.milestones),
            milestones=[
                MilestoneOut(
                    id=m.id,
                    title=m.title,
                    due_date=m.due_date,
                    done=m.done,
                    past_due=not m.done and m.due_date < ctx.today,
                )  # fmt: skip
                for m in r.milestones
            ],
        )
        for r in rocks
    ]
