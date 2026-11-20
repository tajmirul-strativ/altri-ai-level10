from fastapi import APIRouter
from sqlalchemy import select

from app.deps import CurrentUser, Db, ReadTeam, accessible_team_ids
from app.models import Team, TeamMembership, User
from app.schemas import TeamOut, TeamRef, UserOption

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", summary="Teams the user can open (every team for Admins)")
def list_teams(db: Db, user: CurrentUser) -> list[TeamRef]:
    ids = accessible_team_ids(db, user)
    teams = db.scalars(select(Team).where(Team.id.in_(ids)).order_by(Team.name))
    return [TeamRef(id=t.id, name=t.name) for t in teams]


@router.get("/{team_id}", summary="Team, its members and the current weeks")
def get_team(ctx: ReadTeam) -> TeamOut:
    members = ctx.db.scalars(
        select(User)
        .join(TeamMembership, TeamMembership.user_id == User.id)
        .where(TeamMembership.team_id == ctx.team.id)
        .order_by(User.name)
    )
    return TeamOut(
        id=ctx.team.id,
        name=ctx.team.name,
        members=[UserOption(id=u.id, name=u.name, role=u.role) for u in members],
        can_write=ctx.can_write,
        today=ctx.today,
        current_week=ctx.current_week,
        last_closed_week=ctx.last_closed_week,
    )
