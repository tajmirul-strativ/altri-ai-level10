# Build log

What was built, why, and what was traded off. Newest last. Design detail: [design.md](design.md). Reviewer-facing summary: [decision-record.md](decision-record.md).

## 2026-11-20 — Docs and expected answer
- Brief, seed and starter README copied from the Drive folder into `docs/`. Design agreed in [design.md](design.md).
- `backend/tests/expected_rules_report.json`: the rules report for the seed, worked out by hand from the spec and cross-checked with a throwaway script. Everything after is tested against it.
- Process: test-first. A failing test is committed (`(red)`) before the code that passes it (`(green)`).

## 2026-11-20 — Test infrastructure and clock
- Postgres in Docker on host port 5433 (a local Postgres uses 5432). `make test` runs everything in Docker; `make test-local` runs backend tests on the host.
- Test DB is migrated and seeded once per session; each test runs in a rolled-back transaction ([conftest.py](../backend/tests/conftest.py)).
- One source of "now": [clock.py](../backend/app/clock.py). `FrozenClock` (tests, rules report) and `RunningClock` (app: starts at `APP_NOW`, then ticks). A frozen app clock would freeze the meeting timer.
- Known limit: restarting the API resets the running clock to `APP_NOW`.

## 2026-11-20 — Business rules
- Pure functions in [rules.py](../backend/app/rules.py); weeks and days in company time in [company_time.py](../backend/app/company_time.py) (zoneinfo, so the 169-hour DST week is correct).
- `Decimal` half-up everywhere (Python's `round` gives 8.2 for 8.25). The 90 % target compares whole numbers, not the rounded percent.
- Choices the spec leaves open: done before the due week counts; Monday 00:00:00 is late; a Complete Rock with Milestones shows its Milestone ratio.
- Renamed planned `app/time.py` to `company_time.py` (clash with stdlib `time`).

## 2026-11-20 — Schema
- One plain-SQL migration: [0001_initial_schema.py](../backend/migrations/versions/0001_initial_schema.py). CHECKs for every enum/range, composite FKs keep sources and owners inside the team.
- Partial unique indexes: one unsolved Issue per Measurable+week; one active meeting per team.
- Role rules a FK can't express (Observers can't own/facilitate/rate; non-member Admins may own Issues and facilitate but not own To-Dos) in a trigger raising SQLSTATE 23514, plus the same checks in the API.
- Text ids kept from the seed; new ids continue the style (`i10`, `t42`, `mt3`) from per-table sequences.
- `tests/test_models.py` fails if ORM models drift from the migration.

## 2026-11-20 — Seed, rules report, CLI
- [seed.py](../backend/app/seed.py) inserts missing seed rows only (rerun never overwrites user edits); `reset` truncates and reloads. *Changed from design draft's "upsert".*
- [report.py](../backend/app/report.py) uses the same rule functions as the API. `make rules-report` (= `python -m app.cli rules-report --fresh`) runs on a throwaway seeded database so app data is never touched. Output committed as `rules_report.json`.
- Meeting summary ([summary.py](../backend/app/summary.py)) counts Issues solved / To-Dos created by the meeting's time window. *Changed from the earlier agreed `meeting_id` column:* one rule for seeded and new meetings. Summaries are computed live; freezing them at End is described only (brief allows).

## 2026-11-20 — REST API and authorization
- Every team route depends on `read_team` / `write_team` ([deps.py](../backend/app/deps.py)). Unknown or inaccessible team → 403 (same response, so ids can't be probed). Records reached through the wrong team → 404.
- Session: signed httpOnly cookie holding the user id ([session.py](../backend/app/session.py)); user picker login (spec allows).
- Make it an Issue: `INSERT … ON CONFLICT DO NOTHING` on the partial index, then select ([services/issues.py](../backend/app/services/issues.py)). Verified the concurrency test fails against a naive check-then-insert.
- Meeting advance is a conditional update (`WHERE section = :from`); a stale click gets 409.
- Inputs forbid unknown fields; strict ints/bools so `"8"` or `"yes"` are rejected.

## 2026-11-20 — Live updates (SSE)
- Writes call `pg_notify` inside their transaction ([events.py](../backend/app/events.py)), so only committed changes are announced. One LISTEN connection per process fans out to SSE streams ([realtime.py](../backend/app/realtime.py)).
- Events only name what changed; browsers re-read over REST, the same path as reconnect recovery. *Changed from design draft,* which pushed full meeting state.
- Rejected WebSocket: updates only flow server→browser; SSE reconnects by itself and carries the cookie.

## 2026-11-20 — Frontend
- Next.js 16 + shadcn/ui (Base UI flavour) + TanStack Query + react-hook-form/zod. Types generated from OpenAPI (`pnpm gen:api`).
- Used lightly: client-rendered pages, `/api` proxied to FastAPI via rewrites (one origin, first-party cookie). `cacheComponents` off (live per-user data).
- `compress: false` in [next.config.ts](../frontend/next.config.ts): gzip held back SSE through the proxy.
- Times shown in company time ([time.ts](../frontend/src/lib/time.ts)); the browser never computes weeks.
- Timer: server sends `section_started_at` + `server_now`; the browser corrects for its own clock offset ([use-section-timer.ts](../frontend/src/hooks/use-section-timer.ts)).
- Not using the Strativ design skill: the brief requires shadcn/ui and this is an Altri submission.

## 2026-11-21 — Docker and end-to-end test
- Frontend image is a Next standalone build; `docker compose up` starts db, API (migrate + seed + serve) and web.
- Two-browser Playwright test ([meeting-sync.spec.ts](../frontend/e2e/meeting-sync.spec.ts)) runs in the Playwright image via `make test`; traces of failures land in `frontend/test-results/`.
- E2E assertions don't depend on the clock, so the stack keeps its running clock.

## 2026-11-21 — Submission docs
- [README.md](../README.md): run, test, rules report, fixtures/clock note, assumptions, limitations, AI tools (draft — owner to confirm).
- [decision-record.md](decision-record.md) rewritten as the one-page answer to brief 2.8. Summary snapshot (§5) described, not built.

## 2026-11-21 — To-Dos grouped by Issue
- Meeting panel "New To-Dos from this meeting" groups To-Dos under their Issue (open Issues in Issue order, then solved ones with a Solved badge) instead of a link line per To-Do ([conclude-panel.tsx](../frontend/src/features/meeting/conclude-panel.tsx)).
- Each open Issue shows a "N To-Dos · M done" chip ([issues-section.tsx](../frontend/src/features/issues/issues-section.tsx)), so the link reads both ways.
- Rejected: nesting To-Dos inside Issue cards — solving an Issue removes it from the open list and its To-Dos would vanish.
- Timer shows minutes past 60 as "60:00", not "1:00:00".

## 2026-11-21 — Clock survives restarts; Issue To-Dos expand inline
- **Clock:** the running clock's start (wall time, per APP_NOW) is stored in `app_clock` (migration 0002); every process computes `APP_NOW + elapsed since that start` ([clock.py](../backend/app/clock.py)). *Reverses the 2026-11-20 limitation* where each API restart jumped back to APP_NOW, giving new rows earlier timestamps than old ones and freezing live timers. `make reset` clears it and restarts the API.
- **Issue To-Dos:** the "N To-Dos" chip on an Issue expands that Issue's To-Dos inline, from any meeting ([issues-section.tsx](../frontend/src/features/issues/issues-section.tsx)). The meeting panel still lists only this meeting's new To-Dos (brief: Conclude recaps the meeting's new To-Dos).

## 2026-11-21 — Meeting panel shows all Issue To-Dos
- Panel renamed "To-Dos by Issue": every To-Do linked to an Issue, grouped by Issue; ones created in the current meeting get a **New** badge (keeps the brief's Conclude recap of new To-Dos). Unlinked To-Dos stay on the Team page.
- The Issue "N To-Dos" chip is a plain count badge again. *Reverses the inline-expand chip from the previous entry*, per owner request.

## 2026-11-21 — Section hint is a muted subtitle
- The per-section agenda hint moved from a bordered info `Alert` to one line of muted text under the meeting title ([meeting-view.tsx](../frontend/src/features/meeting/meeting-view.tsx)). Weekly attendees stop reading alert boxes; the hint still guides newcomers without taking space. Rejected: removing hints (EOS newcomers lose the flow) and a dismiss toggle (extra state for little gain).
