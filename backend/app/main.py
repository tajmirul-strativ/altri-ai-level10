"""FastAPI application. OpenAPI docs at /api/docs."""

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import errors
from app.api import auth, issues, meetings, scorecard, teams, todos_rocks
from app.db import get_db

app = FastAPI(
    title="Level 10 Meeting API",
    description=(
        "Weekly Measurables, Rocks, To-Dos and Issues, and the Level 10 Meeting. "
        "Sign in with POST /api/auth/login; the session is a signed httpOnly cookie. "
        "Errors: 401 no session, 403 no access to the team or role not allowed, "
        "404 not found in this team, 409 conflicts with current state, 422 invalid input."
    ),
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
errors.install(app)

for router in (auth, teams, scorecard, issues, todos_rocks, meetings):
    app.include_router(router.router)


@app.get("/api/health", tags=["meta"])
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
