# Design: Level 10 Meeting app

Status: **agreed** (2026-11-20). No code yet. This doc is the contract the tests are written against (we build test-first), and it is the source for the one-page decision record (brief 2.8).

Spec: [assessment-brief.md](assessment-brief.md) · Report format: [starter-README.md](starter-README.md) · Seed: [seed.json](seed.json)

---

## 1. Scope

Build every requirement in brief 2.5–2.7. **No bonus items** until the core is done.

Stack (fixed by the brief): Next.js + TypeScript + shadcn/ui + Tailwind · FastAPI · Postgres · SQLAlchemy 2 + Alembic.

## 2. Time and the clock

Time logic lives in two backend modules: `app/clock.py` (the only source of "now") and `app/company_time.py` (weeks, days and quarters in company time). Nothing else reads the clock or converts time zones.

| Concept | Definition |
| --- | --- |
| Storage | Every timestamp is `timestamptz`, stored in UTC. Due dates and week starts are plain `date` values (company calendar). |
| `now()` | Read from an injectable `Clock`. Never from `datetime.now()`. |
| `today` | `now()` converted to America/Chicago, date part. |
| `week_of(date)` | The Monday on or before that date. A week is named by its Monday (`week_start`). |
| `week_bounds(week_start)` | `[Monday 00:00, next Monday 00:00)` in Chicago, converted to UTC with `zoneinfo`. Respects daylight saving: the week of Oct 26 2026 is 169 hours long. |
| `week_of_instant(ts)` | Convert the UTC timestamp to Chicago, then `week_of` its date. |
| current week | `week_of(today)` |
| last closed week | current week − 7 days |
| shown weeks | the 13 weeks from current − 12 weeks to current |

**Clock modes**

- `frozen`: `now()` always returns `APP_NOW`. Used by every test and by the rules report command.
- `running` (the app default under `docker compose up`): `now()` = `APP_NOW` + time elapsed since the server process started. The demo starts at the seed's "now" and the meeting timer actually moves.
- `APP_NOW` defaults to `2026-11-11T15:00:00Z`.
- Known limitation: restarting the server resets the running clock to `APP_NOW`. Rows created in an earlier run can then sit in the "future". Acceptable for a demo; noted in the README.

**Rounding**: every percentage and the meeting rating use `Decimal` with `ROUND_HALF_UP`. Never `round()` or floats. The 90 % target compares the exact fraction (`done * 10 >= due * 9`), not the rounded percent.

**Numbers**: scores and goals are `NUMERIC` in Postgres and `Decimal` in Python, so `3.0 <= 3.0` and `exactly 1` compare exactly.

## 3. Data model

IDs are `text`. Seed IDs are kept as-is (`u1`, `m1`, `t12`). New rows get a prefix plus the next number from a per-table sequence (`i10`, `t42`, `mt3`). The seed script moves each sequence past the highest seeded number.

```
company 1─* users            (role: admin | team_member | observer)
company 1─* teams
teams   *─* users            via team_memberships
teams   1─* measurables 1─* scores        (one per measurable per week)
teams   1─* rocks       1─* milestones
teams   1─* issues      ─0..1→ (measurable, week)   "source" of Make it an Issue
teams   1─* todos       ─0..1→ issue                "source_issue"
teams   1─* meetings    1─* meeting_attendees 1─0..1 meeting_ratings
```

### Tables

| Table | Columns | Database constraints |
| --- | --- | --- |
| `companies` | id, name, timezone | — |
| `users` | id, company_id, name, email, role | `email` unique; `role` CHECK in (admin, team_member, observer) |
| `teams` | id, company_id, name | — |
| `team_memberships` | team_id, user_id | PK (team_id, user_id) |
| `measurables` | id, team_id, name, owner_id, unit, goal_type, goal_value, goal_min, goal_max | `goal_type` CHECK; shape CHECK: `between` needs min ≤ max and no value; the other three need value and no min/max. Owner FK `(team_id, owner_id)` → `team_memberships` |
| `scores` | measurable_id, week_start, value, updated_at, updated_by | PK (measurable_id, week_start); CHECK week_start is a Monday |
| `rocks` | id, team_id, title, owner_id, quarter, status | `quarter` CHECK `YYYY-Qn`; `status` CHECK in (on_track, off_track, complete); owner FK → membership |
| `milestones` | id, rock_id, title, due_date, done | — |
| `issues` | id, team_id, title, owner_id, priority, created_at, solved_at, resolution_note, source_measurable_id, source_week_start | `priority` NULL or 1–5; title not blank; solved_at and resolution_note both NULL or both set (note not blank); source columns both NULL or both set; source FK `(source_measurable_id, team_id)` → `measurables(id, team_id)`, so a source is always in the same team; owner FK → `users` (an Admin may own an Issue in any team); **partial unique index** on `(source_measurable_id, source_week_start) WHERE solved_at IS NULL` |
| `todos` | id, team_id, title, owner_id, due_date, done_at, source_issue_id, created_at | title not blank; source FK `(source_issue_id, team_id)` → `issues(id, team_id)`; owner FK → membership |
| `meetings` | id, team_id, facilitator_id, started_at, ended_at, section, section_started_at | facilitator FK → `users`; `section` CHECK in (scorecard, ids, conclude); ended_at ≥ started_at; **partial unique index** on `(team_id) WHERE ended_at IS NULL` (one active meeting per team) |
| `meeting_attendees` | meeting_id, user_id, joined_at | PK (meeting_id, user_id); user FK → `users` |
| `meeting_ratings` | meeting_id, user_id, rating, updated_at | PK (meeting_id, user_id); rating CHECK 1–10; FK `(meeting_id, user_id)` → `meeting_attendees` (only attendees rate) |

**Ownership and role checks in the database.** Two kinds of people column:
- *Must be a team member*: To-Do owners (agreed rule: the team's own Admins and Team Members), plus the seeded Measurable and Rock owners. Composite FK `(team_id, owner_id)` → `team_memberships`.
- *Team member or any Admin*: Issue owners, facilitators, attendees, raters. Admins act in every team, so an Admin who isn't a member can still click Make it an Issue (and own the result) or run a Sales meeting. Plain FK → `users`.

What a foreign key can't express — "member **or** Admin", and "Observers can't own, facilitate or rate" — a small trigger enforces. The API checks the same rules first and returns a clean 403/422; the trigger is the safety net.

**How Issues and To-Dos link to their sources.**
- Issue → Measurable + week: two nullable columns on `issues`, not a separate table. One source type in the core, so a polymorphic link table would be overhead. The partial unique index sits directly on those columns.
- To-Do → Issue: nullable `source_issue_id`. To-Dos made from the To-Dos section have none.
- Meeting → Issues solved / To-Dos created: **derived from time**, not stored. An Issue counts as solved in a meeting when the meeting's team matches and `solved_at` falls within `[started_at, ended_at]`. Same for To-Dos and `created_at`.
  - **Change from earlier plan:** we had agreed to store a `meeting_id`. The time window is simpler and matches the brief's wording ("solved … during the meeting"). It treats seeded and new meetings with one rule, and it also counts work done from the Team page while the meeting runs. Cost: an Issue solved outside the meeting but during its time span still counts, which is arguably correct. Tell me if you'd rather keep `meeting_id`.

**Past meeting summaries.** The summary is computed from current data, so editing an old week's score would change an old meeting's summary. The brief only asks us to describe the fix: when a meeting ends, write the computed summary as JSON into a `meetings.summary` column (or a `meeting_summaries` table) and serve that copy from then on. Not built, to keep the core small.

## 4. Business rules (pure functions)

`app/rules.py`: no database, no clock. Every input is passed in, so every rule is unit-tested with boundary cases.

| Function | Rule |
| --- | --- |
| `measurable_status(goal, score, week, current_week)` | Score present: compare (`>=`, `<=`, `min ≤ v ≤ max`, `==`). Boundaries are on track. Score missing: `pending` if `week == current_week`, else `off_track`. |
| `todo_completion(todos, week_start, now)` | due = To-Dos with `due_date` in that week. done = those with `done_at` before the week's end **and** `done_at ≤ now`. 0 due → `None`. Else `{due, done, rate_percent, meets_target}`. |
| `is_overdue(todo, today)` | not done and `due_date < today` |
| `rock_status(rock, milestones, today)` | seeded `complete` → complete; seeded `off_track` → off_track; any milestone not done with `due_date < today` → off_track; else on_track |
| `rock_progress(rock, milestones)` | No milestones: 100 if complete, else 0. Otherwise done ÷ total, rounded half up. |
| `issue_sort_key(issue)` | priority descending, no priority last, then `created_at` ascending, then id |
| `meeting_rating(ratings)` | average to 1 decimal, rounded half up; no ratings → `None` |
| `scorecard_week(meeting)` | `week_of_instant(started_at)` − 7 days |

The **rules report** command (`python -m app.cli rules-report`) loads the database, calls these functions, and prints the JSON in the starter README's format. Using the same functions guarantees the report and the UI agree.

## 5. Authentication and authorization

- **Login**: a user picker. `POST /api/auth/login {user_id}` sets a signed, httpOnly, SameSite=Lax session cookie. The server never trusts a user id sent by the client.
- **Team access**: Admin → every team. Others → teams they're members of.
- **Writes**: Admin and Team Member only, and only in teams they can access.

Every team-scoped route goes through one dependency, `team_access(team_id, need="read"|"write")`. The route can't run without passing it.

| Situation | Status |
| --- | --- |
| No or invalid session | 401 |
| Team not accessible to the user, **including a team id that doesn't exist** (same response, so ids can't be probed) | 403 |
| Role not allowed (Observer write, non-facilitator advancing) | 403 |
| Resource not found inside an accessible team | 404 |
| Valid request that conflicts with current state (meeting already active, stale advance, rating after end, Make it an Issue on a cell that isn't off track) | 409 |
| Invalid input | 422 |

Error body: `{"detail": "<message>", "code": "<machine_code>"}`.

## 6. REST API

Prefix `/api`. JSON. OpenAPI docs at `/api/docs`; the frontend's TypeScript types are generated from that schema. Every team resource is nested under `/teams/{team_id}`, so the access check is always the same.

| Method & path | Who | Notes |
| --- | --- | --- |
| `GET /auth/users` | anyone | Seeded users, for the picker |
| `POST /auth/login` · `POST /auth/logout` · `GET /auth/me` | — | |
| `GET /teams` | signed in | Teams for the switcher |
| `GET /teams/{t}` | read | Team plus members and roles (for owner dropdowns) |
| `GET /teams/{t}/scorecard` | read | Measurables × 13 weeks: value and status per cell, plus `current_week` and `last_closed_week` |
| `PUT /teams/{t}/measurables/{m}/scores/{week}` | write | `{value}`; any of the 13 shown weeks; last save wins |
| `DELETE /teams/{t}/measurables/{m}/scores/{week}` | write | Clear a score |
| `POST /teams/{t}/measurables/{m}/scores/{week}/issue` | write | Make it an Issue. **201** new Issue, **200** existing open one. 409 if the cell isn't off track. |
| `GET /teams/{t}/issues?status=open\|solved` | read | Open ones in Issue order; solved ones by `solved_at` descending |
| `POST /teams/{t}/issues` | write | `{title, priority?}`; owner = caller |
| `PATCH /teams/{t}/issues/{i}` | write | `{priority}` (1–5 or null) |
| `POST /teams/{t}/issues/{i}/solve` | write | `{note}` required |
| `POST /teams/{t}/issues/{i}/todos` | write | `{title, owner_id}`; due = today + 7 days |
| `GET /teams/{t}/todos` | read | Includes `overdue` per To-Do and `last_closed_week_completion` |
| `PATCH /teams/{t}/todos/{td}` | write | `{done: true\|false}` sets or clears `done_at` |
| `GET /teams/{t}/rocks` | read | Current quarter, with milestones, computed status and progress |
| `GET /teams/{t}/meetings/active` | read | Meeting state or 404 |
| `POST /teams/{t}/meetings` | write | Start; caller becomes facilitator. 409 + active meeting id if one is running. |
| `GET /teams/{t}/meetings/{mt}` | read | Full meeting state (see §7) |
| `POST /teams/{t}/meetings/{mt}/join` | read | Idempotent; Observers can join |
| `POST /teams/{t}/meetings/{mt}/advance` | facilitator | `{from_section}`; 409 if the meeting has already moved past it |
| `POST /teams/{t}/meetings/{mt}/end` | facilitator | Any section |
| `PUT /teams/{t}/meetings/{mt}/rating` | write + attendee | `{rating: 1–10}`; only in Conclude, before the end; can change |
| `GET /teams/{t}/meetings/{mt}/summary` | read | Ended meetings only, seeded ones included |
| `GET /teams/{t}/events` | read | SSE stream (see §7) |

## 7. Real-time meetings

**Transport: Server-Sent Events plus REST.** Every change goes through a normal REST call. The server then pushes an event to everyone watching that team. Updates only flow server → browser, which is what SSE does; `EventSource` reconnects by itself and sends the session cookie with no extra work. WebSocket would add a two-way channel we don't need.

**Ownership: the database owns meeting state.** `meetings.section` and `section_started_at` are the truth. Nothing important lives only in server memory. Why these two columns (not in the seed) and the rejected alternatives: [decision-record.md §3](decision-record.md).

**Flow**

1. A write commits, then calls `pg_notify('team_events', {team_id, type, payload})`.
2. Each API process `LISTEN`s and forwards the event to its SSE subscribers for that team. Works with several server processes.
3. One event type, `change`, saying **what** changed: `{"resources": ["issues"]}`, plus `meeting_id` for meeting changes. Resources: `scorecard`, `issues`, `todos`, `meeting`. The browser re-reads those through TanStack Query (for `meeting`: `GET …/meetings/{id}`). The stream starts with `ready`.
   - *Changed from the first draft*, which pushed the full meeting state in the event. Re-reading is one extra request (well inside the ~1 s budget) and uses exactly the same path as recovery after a reconnect, so there's one code path to get right.
4. A heartbeat every 15 s keeps proxies from closing the stream.

**Timer.** The server sends `section_started_at` and `server_now`. The browser computes the offset between its own clock and `server_now`, and counts up locally. Elapsed time over the section's limit shows as "N min over". Nothing advances automatically.

**Recovery.** On every (re)connect, including the first load, a refresh, or the facilitator reconnecting, the browser fetches `GET …/meetings/{mt}` and invalidates all team data. Missed events don't matter because the full state is re-read.

**Concurrency**

| Case | Mechanism |
| --- | --- |
| Make it an Issue, two clicks at once | One transaction: check the cell is off track, then `INSERT … ON CONFLICT (source_measurable_id, source_week_start) WHERE solved_at IS NULL DO NOTHING RETURNING *`. If nothing is returned, `SELECT` the open Issue. Postgres makes the second insert wait for the first to commit, then skip, so both callers get the same Issue. |
| Two people start a meeting | Same pattern on the one-active-meeting index. The loser gets 409 with the active meeting's id and joins it. |
| Facilitator double-clicks Next | `UPDATE meetings SET section = :next, section_started_at = now WHERE id = :id AND section = :from AND ended_at IS NULL`. 0 rows updated → 409. |
| Two people edit one score | Upsert; last save wins (as the brief says). |
| Rating changed twice | Upsert on (meeting, user). |

## 8. Frontend

**Why Next.js, and how it's used.** Left to my own choice I would build this frontend with plain React (a Vite single-page app). It's a signed-in, highly interactive app with live updates, no need for search-engine visibility, and all data and logic in FastAPI, so Next.js's server features (server rendering, server components, server actions) have little to do. The brief explicitly specifies Next.js, though, and there wasn't time to ask for a change and wait for a reply before the deadline. So the app uses Next.js, deliberately in a light way: App Router for routing and layouts, client components for the pages, rewrites to proxy `/api` to FastAPI. No server actions and no database access from Next.js.

- Next.js App Router. Pages: `/login`, `/teams/[teamId]`, `/teams/[teamId]/meetings/[meetingId]`.
- **TanStack Query** for all server data. One `useTeamEvents(teamId)` hook opens the SSE stream, writes `meeting` events into the cache, and invalidates queries on `invalidate` events.
- `ScorecardSection` and `IssuesSection` are built once and used on both pages, as the brief requires. Observers get the same components with actions hidden; the server still refuses their writes.
- Forms: react-hook-form + zod.
- API calls go through Next.js rewrites (`/api/*` → FastAPI), so the browser sees one origin and the cookie just works. Risk: some proxies buffer SSE. If that happens, the browser connects to FastAPI directly for `/events` only.

### Display time zone

UTC is for storage and the API only. The browser shows **company time**, not UTC and not the viewer's own zone.

- **Source.** The company time zone is defined by the spec (brief 2.6 and 2.7, starter README, `seed.json` → `company.timezone` = `America/Chicago`). The code reads it from `companies.timezone`; it is never hard-coded.
- **Why company time.** Weeks, due dates and "overdue" are all defined in company time. Showing another zone makes the screen contradict the rules. Example: t28 was done at `2026-11-09T05:59Z`. In Chicago that's Sun Nov 8, 11:59 PM, inside its due week, which is why it counts as done. In UTC or GMT+6 it would read as Monday, after the week.
- The brief only defines the company time zone; choosing it for display is our decision.

| Value | API sends | Browser shows |
| --- | --- | --- |
| Timestamps (created, done, solved, meeting start/end) | UTC ISO 8601 | Formatted in company time, labelled "CT" |
| Due dates, week starts, milestone dates | Plain date (`2026-11-06`) | As-is, no conversion |
| Meeting timer | `section_started_at` + `server_now` | A duration (`4:32`); no time zone involved |
| Today, current week, last closed week, overdue flags | Computed by the server | Displayed as received |

- `GET /auth/me` returns the company time zone with the user.
- One frontend helper, `formatTimestamp(iso)`, formats with `Intl.DateTimeFormat(..., { timeZone })`. Nothing else formats times.
- The browser never computes week boundaries or "today".

## 9. Testing (test-first)

One command: `make test` runs backend tests, then Playwright, unattended.

| Layer | Tool | Database / clock |
| --- | --- | --- |
| Rule tests | pytest | None / passed in |
| Constraint tests | pytest | Test DB; each test in a rolled-back transaction |
| Rules report test | pytest | Fresh seed, frozen `APP_NOW`; output must equal `tests/expected_rules_report.json`, which is **worked out by hand from the spec and reviewed before code exists** |
| API tests | pytest + httpx | Same per-test rollback. Concurrency tests commit for real, so they use a separate database that is re-seeded afterwards |
| Real-time tests | pytest | SSE client receives the event after a write; reconnect gets current state |
| End-to-end | Playwright, 2 browser contexts | Full stack in Docker, frozen clock, trace kept on failure (the required failure artifact) |

Clock in tests: the `Clock` dependency is overridden per test, so a test can stand one minute before a week boundary.

Commits: a failing test is committed before the code that makes it pass.

## 10. Repository layout

```
backend/        FastAPI app, Alembic migrations, seed + rules-report CLI, pytest suite
frontend/       Next.js app
e2e/            Playwright test + config
docs/           brief, seed, this design, decision record
docker-compose.yml · Makefile · README.md · rules_report.json
```

`docker compose up` starts Postgres, runs migrations and the seed (safe to rerun: inserts missing seed rows, never overwrites existing ones), then starts the API and the frontend.

## 11. Resolved decisions (2026-11-20)

1. Meetings link to Issues solved and To-Dos created by time window, not a stored `meeting_id` (§3).
2. Rerunning the seed inserts only missing seed rows: it never overwrites existing rows, so user edits and user-created data survive. `make reset` wipes and re-seeds for a "freshly seeded" database (rules report).
3. Observer and "member or Admin" checks are enforced twice: in the API (clean errors) and by a database trigger (safety net) (§3).
4. An Admin who isn't a team member can own Issues, facilitate, attend and rate in that team, but can't own To-Dos there (§3).
5. Frontend stays on Next.js as the brief requires, used lightly (§8).
