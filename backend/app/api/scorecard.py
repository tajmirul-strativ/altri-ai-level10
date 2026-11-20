from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Response
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.company_time import shown_weeks
from app.deps import ReadTeam, TeamContext, WriteTeam
from app.errors import conflict, invalid, not_found
from app.events import publish
from app.models import Issue, Measurable, Score
from app.rules import measurable_status
from app.schemas import (
    CellOut,
    GoalOut,
    IssueOut,
    MeasurableRow,
    ScorecardOut,
    ScoreIn,
)
from app.services.issues import make_it_an_issue
from app.services.views import issue_out, user_ref

router = APIRouter(prefix="/api/teams/{team_id}", tags=["scorecard"])


def _measurable(ctx: TeamContext, measurable_id: str) -> Measurable:
    m = ctx.db.get(Measurable, measurable_id)
    if m is None or m.team_id != ctx.team.id:
        raise not_found("Measurable")
    return m


def _shown_week(ctx: TeamContext, week: date) -> date:
    if week not in shown_weeks(ctx.now, ctx.tz):
        raise invalid("Week must be a Monday within the 13 weeks shown on the Scorecard.")
    return week


def _open_issue_ids(ctx: TeamContext, ids: list[str]) -> dict[tuple[str, date], str]:
    rows = ctx.db.execute(
        select(Issue.source_measurable_id, Issue.source_week_start, Issue.id).where(
            Issue.source_measurable_id.in_(ids), Issue.solved_at.is_(None)
        )
    )
    return {(m, w): i for m, w, i in rows}


def _cell(
    ctx: TeamContext, m: Measurable, week: date, value: Decimal | None, issue_id: str | None
) -> CellOut:
    return CellOut(
        week_start=week,
        value=value,
        status=measurable_status(m.goal, value, week, ctx.current_week),
        open_issue_id=issue_id,
    )


def _cell_now(ctx: TeamContext, m: Measurable, week: date) -> CellOut:
    score = ctx.db.get(Score, (m.id, week), populate_existing=True)
    return _cell(ctx, m, week, score.value if score else None,
                 _open_issue_ids(ctx, [m.id]).get((m.id, week)))  # fmt: skip


@router.get("/scorecard", summary="Measurables × the last 13 weeks, with status per cell")
def get_scorecard(ctx: ReadTeam) -> ScorecardOut:
    weeks = shown_weeks(ctx.now, ctx.tz)
    measurables = ctx.db.scalars(
        select(Measurable).where(Measurable.team_id == ctx.team.id).order_by(Measurable.id)
    ).all()
    ids = [m.id for m in measurables]
    scores = {
        (s.measurable_id, s.week_start): s.value
        for s in ctx.db.scalars(
            select(Score).where(
                Score.measurable_id.in_(ids), Score.week_start.between(weeks[0], weeks[-1])
            )
        )
    }
    open_issues = _open_issue_ids(ctx, ids)
    return ScorecardOut(
        weeks=weeks,
        current_week=ctx.current_week,
        last_closed_week=ctx.last_closed_week,
        measurables=[
            MeasurableRow(
                id=m.id,
                name=m.name,
                unit=m.unit,
                owner=user_ref(ctx.db, m.owner_id),
                goal=GoalOut(type=m.goal_type, value=m.goal_value, min=m.goal_min, max=m.goal_max),
                cells=[
                    _cell(ctx, m, w, scores.get((m.id, w)), open_issues.get((m.id, w)))
                    for w in weeks
                ],
            )
            for m in measurables
        ],
    )


@router.put(
    "/measurables/{measurable_id}/scores/{week_start}",
    summary="Set a score (last save wins)",
)
def put_score(ctx: WriteTeam, measurable_id: str, week_start: date, body: ScoreIn) -> CellOut:
    m = _measurable(ctx, measurable_id)
    week = _shown_week(ctx, week_start)
    ctx.db.execute(
        insert(Score)
        .values(
            measurable_id=m.id,
            week_start=week,
            value=body.value,
            updated_at=ctx.now,
            updated_by=ctx.user.id,
        )  # fmt: skip
        .on_conflict_do_update(
            index_elements=["measurable_id", "week_start"],
            set_={"value": body.value, "updated_at": ctx.now, "updated_by": ctx.user.id},
        )
    )
    publish(ctx.db, ctx.team.id, ["scorecard"])
    ctx.db.commit()
    return _cell_now(ctx, m, week)


@router.delete(
    "/measurables/{measurable_id}/scores/{week_start}", status_code=204, summary="Clear a score"
)
def delete_score(ctx: WriteTeam, measurable_id: str, week_start: date) -> None:
    m = _measurable(ctx, measurable_id)
    week = _shown_week(ctx, week_start)
    ctx.db.execute(delete(Score).where(Score.measurable_id == m.id, Score.week_start == week))
    publish(ctx.db, ctx.team.id, ["scorecard"])
    ctx.db.commit()


@router.post(
    "/measurables/{measurable_id}/scores/{week_start}/issue",
    status_code=201,
    summary="Make it an Issue: 201 with a new Issue, or 200 with the existing unsolved one",
)
def post_make_issue(
    ctx: WriteTeam, measurable_id: str, week_start: date, response: Response
) -> IssueOut:
    m = _measurable(ctx, measurable_id)
    week = _shown_week(ctx, week_start)
    if _cell_now(ctx, m, week).status != "off_track":
        raise conflict("not_off_track", "Only an off-track score can be made into an Issue.")
    issue, created = make_it_an_issue(ctx.db, m, week, ctx.user, ctx.now)
    if created:
        publish(ctx.db, ctx.team.id, ["issues", "scorecard"])
    ctx.db.commit()
    if not created:
        response.status_code = 200
    return issue_out(ctx.db, issue)
