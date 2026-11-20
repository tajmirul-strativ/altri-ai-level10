"""Request dependencies: the signed-in user and team access (design.md §5).

Every team route depends on `read_team` or `write_team`, so no handler can run without the
access check. An unknown team id gets the same 403 as a team the user can't see.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Cookie, Depends, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import Clock, get_clock
from app.company_time import current_week, last_closed_week, today
from app.db import get_db
from app.errors import forbidden, unauthorized
from app.models import Team, TeamMembership, User
from app.session import COOKIE, read_session

Db = Annotated[Session, Depends(get_db)]
ClockDep = Annotated[Clock, Depends(get_clock)]


def current_user(db: Db, session: Annotated[str | None, Cookie(alias=COOKIE)] = None) -> User:
    user_id = read_session(session)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def is_member(db: Session, team_id: str, user_id: str) -> bool:
    return db.get(TeamMembership, (team_id, user_id)) is not None


def accessible_team_ids(db: Session, user: User) -> list[str]:
    if user.role == "admin":
        return list(db.scalars(select(Team.id).order_by(Team.id)))
    return list(
        db.scalars(
            select(TeamMembership.team_id)
            .where(TeamMembership.user_id == user.id)
            .order_by(TeamMembership.team_id)
        )
    )


@dataclass
class TeamContext:
    """Everything a team route needs: the team, the caller, and time in company terms."""

    db: Session
    team: Team
    user: User
    now: datetime
    tz: ZoneInfo

    @property
    def can_write(self) -> bool:
        return self.user.role != "observer"

    @property
    def today(self) -> date:
        return today(self.now, self.tz)

    @property
    def current_week(self) -> date:
        return current_week(self.now, self.tz)

    @property
    def last_closed_week(self) -> date:
        return last_closed_week(self.now, self.tz)


def read_team(
    team_id: Annotated[str, Path()], db: Db, user: CurrentUser, clock: ClockDep
) -> TeamContext:
    team = db.get(Team, team_id)
    if team is None or (user.role != "admin" and not is_member(db, team_id, user.id)):
        raise forbidden("You don't have access to this team.")
    return TeamContext(db, team, user, clock.now(), ZoneInfo(team.company.timezone))


def write_team(ctx: Annotated[TeamContext, Depends(read_team)]) -> TeamContext:
    if not ctx.can_write:
        raise forbidden("Observers can view this team but can't change anything.")
    return ctx


ReadTeam = Annotated[TeamContext, Depends(read_team)]
WriteTeam = Annotated[TeamContext, Depends(write_team)]
