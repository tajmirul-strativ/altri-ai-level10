"""Helpers for creating and migrating test databases."""

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import make_url


def recreate_database(url: str) -> None:
    """Drop and create the database named in `url` (connects to `postgres` on the same server)."""
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


def drop_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)'))
    admin.dispose()


def alembic(connection: Connection, action: str, revision: str) -> None:
    """Run `alembic upgrade|downgrade <revision>` on the given connection."""
    cfg = Config("alembic.ini")
    cfg.attributes["connection"] = connection
    cfg.attributes["configure_logger"] = False
    getattr(command, action)(cfg, revision)
