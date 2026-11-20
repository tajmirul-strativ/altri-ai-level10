from fastapi import APIRouter, Response
from sqlalchemy import select

from app.deps import CurrentUser, Db
from app.errors import unauthorized
from app.models import Company, User
from app.schemas import CompanyOut, LoginIn, MeOut, UserOption
from app.session import clear_session, set_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _me(db: Db, user: User) -> MeOut:
    company = db.get(Company, user.company_id)
    assert company is not None
    return MeOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        company=CompanyOut(id=company.id, name=company.name, timezone=company.timezone),
    )


@router.get("/users", summary="Seeded users for the sign-in picker")
def list_users(db: Db) -> list[UserOption]:
    users = db.scalars(select(User).order_by(User.id))
    return [UserOption(id=u.id, name=u.name, role=u.role) for u in users]


@router.post("/login", summary="Sign in as a seeded user (sets the session cookie)")
def login(body: LoginIn, response: Response, db: Db) -> MeOut:
    user = db.get(User, body.user_id)
    if user is None:
        raise unauthorized("Unknown user.")
    set_session(response, user.id)
    return _me(db, user)


@router.post("/logout", status_code=204, summary="Sign out")
def logout(response: Response) -> None:
    clear_session(response)


@router.get("/me", summary="The signed-in user")
def me(db: Db, user: CurrentUser) -> MeOut:
    return _me(db, user)
