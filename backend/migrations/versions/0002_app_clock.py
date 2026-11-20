"""Persist when the running clock started, so "now" survives API restarts.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE app_clock (
            id          smallint PRIMARY KEY DEFAULT 1,
            app_now     timestamptz NOT NULL,   -- the APP_NOW this clock started from
            started_at  timestamptz NOT NULL,   -- real (wall) time when it started
            CONSTRAINT ck_app_clock_single_row CHECK (id = 1)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE app_clock")
