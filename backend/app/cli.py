"""Command line: `python -m app.cli {seed,reset,rules-report}`.

seed                  insert missing seed records (safe to rerun; keeps user changes)
reset                 empty every table and load the seed again
rules-report          print every computed rule value as JSON, at APP_NOW, for this database
rules-report --fresh  same, but on a throwaway freshly seeded database (the app database
                      is not touched). This is the documented rules report command.
"""

import argparse
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.report import build_rules_report
from app.seed import load_seed, read_seed, reset_database

BACKEND = Path(__file__).resolve().parents[1]


@contextmanager
def throwaway_database(database_url: str) -> Iterator[Engine]:
    """A new, migrated database next to the app's one, dropped afterwards."""
    url = make_url(database_url)
    target = url.set(database=f"{url.database}_rules_report")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    drop = text(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)')
    with admin.connect() as conn:
        conn.execute(drop)
        conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    engine = create_engine(target)
    try:
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "migrations"))
        cfg.attributes["configure_logger"] = False
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(drop)
        admin.dispose()


def print_report(db: Session) -> None:
    # The report always uses APP_NOW exactly (a frozen clock), never the running clock.
    json.dump(build_rules_report(db, get_settings().app_now), sys.stdout, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("command", choices=["seed", "reset", "rules-report"])
    parser.add_argument(
        "--fresh", action="store_true", help="rules-report on a throwaway seeded database"
    )
    args = parser.parse_args(argv)

    if args.command == "rules-report" and args.fresh:
        with throwaway_database(get_settings().database_url) as engine, Session(engine) as db:
            reset_database(db, read_seed())
            db.commit()
            print_report(db)
        return 0

    with Session(get_engine()) as db:
        if args.command == "seed":
            load_seed(db, read_seed())
            db.commit()
            print("Seed loaded.", file=sys.stderr)
        elif args.command == "reset":
            reset_database(db, read_seed())
            db.commit()
            print("Database reset to the seed.", file=sys.stderr)
        else:
            print_report(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
