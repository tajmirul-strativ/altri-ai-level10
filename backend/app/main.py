"""FastAPI application."""

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

app = FastAPI(
    title="Level 10 Meeting API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.get("/api/health", tags=["meta"])
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
