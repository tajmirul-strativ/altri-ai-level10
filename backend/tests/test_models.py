"""ORM models describe exactly the schema the migrations create."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.db import Base


def test_orm_models_match_migrated_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)

    assert diff == []
