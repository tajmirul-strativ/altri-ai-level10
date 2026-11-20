# Decision record

The five choices brief 2.8 leaves open. Details: [design.md](design.md).

## 1. Data model, and how Issues and To-Dos link to their sources

Postgres tables mirror the domain: companies, users (one role), teams, memberships, measurables + weekly scores (one per Measurable per Monday), rocks + milestones, issues, todos, meetings + attendees + ratings. Seed ids are kept as text; new ids continue the style (`i10`, `t42`).
- **Issue → Measurable + week:** two nullable columns (`source_measurable_id`, `source_week_start`), with a composite FK that keeps the source inside the same team. Simpler than a polymorphic link table while there is one source type; a Rock or To-Do source (bonus) would add columns or a link table.
- **To-Do → Issue:** nullable `source_issue_id`, again same-team by composite FK.
- **Meeting → Issues solved / To-Dos created:** derived from the meeting's time window, not stored. One rule for seeded and new meetings; it also counts work done on the Team page during the meeting.
- **Integrity in the database:** CHECKs for every enum and range, Monday-only week columns, partial unique indexes, and a trigger for role rules a FK can't express (Observers can't own, facilitate or rate). The API checks the same rules first for clean errors.
- **Weeks and time:** timestamps in UTC; weeks are named by their Monday in company time and computed with zoneinfo, so the 169-hour DST week is right.

## 2. API design

REST under `/api`, every team resource nested under `/teams/{team_id}`, so one dependency enforces access on every route. Status codes: 401 no session, 403 no access to the team (unknown ids too) or role not allowed, 404 not found *in this team*, 409 conflicts with current state (stale advance, already solved), 422 invalid input. Requests reject unknown fields. Make it an Issue returns 201 (created) or 200 (existing). OpenAPI at `/api/docs`; the frontend's types are generated from it.

## 3. Real-time transport; who owns meeting state

**Server-Sent Events + REST.** Every change is a normal REST call; the server then tells everyone watching the team *what* changed, and browsers re-read it. Updates only flow server→browser, which is what SSE does; it reconnects on its own and sends the session cookie. WebSocket would add a two-way channel we don't need.
- **Fan-out:** writes call `pg_notify` inside their transaction, so only committed changes are announced and any number of API processes stay in sync.
- **Ownership:** the database owns meeting state: `section` and `section_started_at` on `meetings`. The timer is `server_now − section_started_at`; the browser corrects for its own clock offset. An overrun shows as over time and never advances by itself.
- **Recovery:** on every (re)connect the browser re-reads the meeting and team data. Late joins, refreshes, the facilitator reconnecting and API restarts all land on the same state.
- **Advancing** is a conditional update (`WHERE section = :from`), so a double click can't skip a section.
- *Rejected:* state in server memory (lost on restart, breaks with several processes); a countdown in the DB (writes every second); the facilitator's browser running the timer (drift, lost on refresh).

## 4. Make it an Issue without duplicates

A **partial unique index** allows one unsolved Issue per Measurable and week. The endpoint runs `INSERT … ON CONFLICT DO NOTHING` on that index, then selects the open Issue. If two requests race, Postgres makes the second insert wait for the first to commit, then skip; its select sees the winner's row. Both callers get the same Issue (201 for the creator, 200 for the other). Solving the Issue frees the slot for a new one. Tests fire 12 parallel requests, and a deterministic test holds the first transaction open; a naive check-then-insert fails them.

## 5. Keeping past meeting summaries unchanged (described, not built)

Today a summary is computed from current data, so editing an old week's score would change an old meeting's summary. Fix: when the facilitator ends the meeting, compute the summary in the same transaction and store it (a `meeting_summaries` row with the scorecard week, each Measurable's status *and value*, Issue and To-Do ids *with titles*, attendees and rating). Serve that copy from then on; never recompute. For the two seeded meetings, write the snapshot during seeding. Tradeoff: snapshots are denormalised and won't reflect corrections, which is exactly the point; an audit trail would explain later edits.
