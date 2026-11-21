# Level 10 — weekly team meetings

Track a team's weekly Measurables, quarterly Rocks, To-Dos and Issues, and run the Level 10 Meeting live across browsers. Built for the Senior AI-First Engineer assessment ([brief](docs/assessment-brief.md)).

**Stack:** Next.js 16 + TypeScript + shadcn/ui + Tailwind · FastAPI · Postgres 17 · SQLAlchemy 2 + Alembic · Server-Sent Events.

## Run it

```bash
docker compose up --build        # or: make up
```

- App: http://localhost:3000 — pick a seeded user to sign in (e.g. **Blake Brooks** in one browser, **Casey Cho** in another, both on Leadership).
- API docs (OpenAPI): http://localhost:8000/api/docs
- Postgres is exposed on host port **5433**. Migrations and the seed run on start; the seed is safe to rerun (it only inserts missing rows). `make reset` restores a fresh seed.
- "Now" comes from `APP_NOW` (default `2026-11-11T15:00:00Z`) and then ticks in real time, so meeting timers move. The clock's start is stored, so restarts continue the same timeline; `make reset` starts it again at `APP_NOW`.

## Tests

```bash
make test
```

Runs, unattended in Docker: the backend suite (400 tests: rules with boundary cases, database constraints, migrations, API and authorization, concurrency, live events) and the two-browser Playwright test.

- **Fixtures:** a test database is migrated and seeded once per run; every test runs in a transaction that is rolled back, so each starts from the fresh seed. Concurrency and live-event tests need real commits and use their own scratch database, reset to the seed per test.
- **Clock:** tests use a frozen clock at `APP_NOW` that a test can move (e.g. to one minute before a week boundary). The Playwright test's assertions don't depend on time.
- **Failure artifact:** [trace](docs/artifacts/e2e-failure-trace.zip) and [screenshot](docs/artifacts/e2e-failure-screenshot.png) from a deliberately broken assertion. Open with `npx playwright show-trace docs/artifacts/e2e-failure-trace.zip`. New failures write traces to `frontend/test-results/`.

## Rules report

```bash
make rules-report                                   # at the default APP_NOW
make rules-report APP_NOW=2026-11-16T15:00:00Z      # any other date
```

Prints every computed value from brief 2.6 as JSON, for a **freshly seeded** throwaway database (your app data is untouched). Committed output: [rules_report.json](rules_report.json). It equals [expected_rules_report.json](backend/tests/expected_rules_report.json), which was worked out by hand from the spec before any code existed.

## Docs

- [Decision record](docs/decision-record.md) — the choices in brief 2.8, with tradeoffs (one page).
- [Design](docs/design.md) — data model, API, real-time and testing in detail.
- [Build log](docs/build-log.md) — what was built, in order, and what changed along the way.

## Assumptions

- **Time:** weeks, due dates, "today" and overdue are in company time (America/Chicago, read from the company record). The UI shows all times in company time too, so a To-Do done Sunday 23:59 doesn't look like Monday.
- **Completion rate** of the current week counts only To-Dos done by now. A To-Do done *before* its due week counts as done; done at Monday 00:00:00 is late.
- **Rock progress:** a Complete Rock *with* Milestones shows its Milestone ratio; the 100 % rule applies only without Milestones.
- **Admins** act in every team: they can own Issues, facilitate and rate in teams they don't belong to. **To-Do owners** must be the team's own Admins or Team Members.
- **Meeting summary:** Issues solved and To-Dos created count if they happened between the meeting's start and end.
- **Meeting:** sections only move forward; the facilitator can end at any time. Opening the meeting page joins it. Observers attend but don't rate.
- **Errors:** unknown or inaccessible team → 403 (same response, so team ids can't be probed); a record reached through the wrong team → 404.
- **Frontend framework:** I'd have built this as a plain React (Vite) single-page app: it's signed-in, live and per-user, with all logic in FastAPI. The brief specifies Next.js and there wasn't time to ask, so Next.js is used lightly: client-rendered pages, and its rewrites proxy `/api` to FastAPI so the cookie stays first-party.

## Known limitations

- Past meeting summaries are computed from current data, so editing an old score changes an old summary. The fix (store a copy at End) is described in the decision record, not built.
- Login is a user picker with a signed session cookie: no passwords (sign-up is out of scope).
- One company per deployment; one LISTEN connection per API process (fine for many processes, not tuned for very large fan-out).
- No meeting history page (out of scope); summaries are reachable by URL and API.

## AI tools

<!-- TODO(Tajmirul): confirm or edit this section before submitting. -->
Built with **Claude Code** (Claude Opus 5.5) as a pair programmer: reading the brief, drafting the design, writing tests first and then the code, and running the test suites. I reviewed the decisions and the code. The expected rules report was derived by hand from the spec and cross-checked with a separate throwaway script, not with the app.
