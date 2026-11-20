"""Command line: `python -m app.cli {seed,reset,rules-report}`.

seed          insert missing seed records (safe to rerun; keeps user changes)
reset         empty every table and load the seed again (a freshly seeded database)
rules-report  print every computed rule value as JSON, at APP_NOW
"""

import argparse
import json
import sys

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.report import build_rules_report
from app.seed import load_seed, read_seed, reset_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("command", choices=["seed", "reset", "rules-report"])
    args = parser.parse_args(argv)
    settings = get_settings()

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
            # The report always uses APP_NOW exactly (a frozen clock), never the running clock.
            report = build_rules_report(db, settings.app_now)
            json.dump(report, sys.stdout, indent=2)
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
