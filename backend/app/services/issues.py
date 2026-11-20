"""Make it an Issue without duplicates (design.md §7)."""

from datetime import date, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Issue, Measurable, User


def issue_title(measurable: Measurable, week: date) -> str:
    """Matches the seed's style: "New deals closed, week of Nov 2"."""
    return f"{measurable.name}, week of {week:%b} {week.day}"


def make_it_an_issue(
    db: Session, measurable: Measurable, week: date, user: User, now: datetime
) -> tuple[Issue, bool]:
    """Return the unsolved Issue for this Measurable and week, creating it if there is none.

    INSERT ... ON CONFLICT DO NOTHING on the partial unique index: if another transaction has
    inserted the same cell but not committed yet, Postgres makes this insert wait, then skip.
    The follow-up SELECT (a new snapshot under READ COMMITTED) then sees the winner's row.
    Returns (issue, created).
    """
    inserted_id = db.execute(
        insert(Issue)
        .values(
            team_id=measurable.team_id,
            title=issue_title(measurable, week),
            owner_id=user.id,
            created_at=now,
            source_measurable_id=measurable.id,
            source_week_start=week,
        )
        .on_conflict_do_nothing(
            index_elements=["source_measurable_id", "source_week_start"],
            index_where=text("solved_at IS NULL"),
        )
        .returning(Issue.id)
    ).scalar()
    issue = db.scalars(
        select(Issue)
        .where(
            Issue.source_measurable_id == measurable.id,
            Issue.source_week_start == week,
            Issue.solved_at.is_(None),
        )
        .execution_options(populate_existing=True)
    ).one()
    return issue, inserted_id is not None
