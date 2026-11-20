"""Rules report (brief Part 3, starter README format).

The expected file was worked out by hand from the spec, before any implementation.
"""

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.report import build_rules_report
from app.seed import load_seed, read_seed
from tests.conftest import SEED_NOW, TEST_DATABASE_URL
from tests.dbutil import alembic, drop_database, recreate_database

BACKEND = Path(__file__).resolve().parents[1]
EXPECTED = json.loads((BACKEND / "tests" / "expected_rules_report.json").read_text())

A_WEEK_LATER = datetime(2026, 11, 16, 15, 0, tzinfo=UTC)  # Mon Nov 16, 09:00 CST


def as_json(report: dict[str, Any]) -> Any:
    """What the command prints, parsed back."""
    return json.loads(json.dumps(report))


@pytest.fixture
def seeded(db: Session) -> Session:
    load_seed(db, read_seed())
    return db


def test_report_matches_hand_derived_answer(seeded: Session) -> None:
    assert as_json(build_rules_report(seeded, SEED_NOW)) == EXPECTED


def test_report_is_computed_from_now_not_hard_coded(seeded: Session) -> None:
    report = as_json(build_rules_report(seeded, A_WEEK_LATER))
    lead = report["teams"]["team_lead"]

    assert report["now"] == "2026-11-16T15:00:00Z"
    weeks = list(lead["measurable_status"]["m1"])
    assert (weeks[0], weeks[-1], len(weeks)) == ("2026-08-24", "2026-11-16", 13)
    # Week of Nov 9 is now closed: missing scores turn off track, m5's 520 stays on track.
    assert lead["measurable_status"]["m1"]["2026-11-09"] == "off_track"
    assert lead["measurable_status"]["m5"]["2026-11-09"] == "on_track"
    assert lead["measurable_status"]["m1"]["2026-11-16"] == "pending"
    # More To-Dos are overdue, and Portal beta (due Nov 11) is now past due.
    assert lead["overdue_todos"] == ["t12", "t30", "t31", "t32"]
    assert report["teams"]["team_sales"]["overdue_todos"] == ["t40"]
    assert lead["rocks"]["r1"]["status"] == "off_track"
    assert lead["todo_completion"]["2026-11-09"] == {
        "due": 3, "done": 0, "rate_percent": 0, "meets_target": False,
    }  # fmt: skip


# --- the documented command, end to end ----------------------------------------------------


@pytest.fixture
def scratch_url() -> Iterator[str]:
    url = make_url(TEST_DATABASE_URL).set(database="l10_report_check")
    url_text = url.render_as_string(hide_password=False)
    recreate_database(url_text)
    engine = create_engine(url_text)
    with engine.begin() as conn:
        alembic(conn, "upgrade", "head")
    engine.dispose()
    try:
        yield url_text
    finally:
        drop_database(url_text)


def run_cli(url: str, *args: str, **env: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", *args],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": url, **env},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_cli_reset_then_rules_report_prints_expected_json(scratch_url: str) -> None:
    run_cli(scratch_url, "reset")

    printed = run_cli(scratch_url, "rules-report")

    assert json.loads(printed) == EXPECTED


def test_cli_rules_report_reads_app_now(scratch_url: str) -> None:
    run_cli(scratch_url, "seed")

    printed = run_cli(scratch_url, "rules-report", APP_NOW="2026-11-16T15:00:00Z")

    assert json.loads(printed)["now"] == "2026-11-16T15:00:00Z"
