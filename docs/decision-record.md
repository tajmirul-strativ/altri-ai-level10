# Decision record

Draft. Covers brief section 2.8; must fit on one page when finished. Full detail lives in [design.md](design.md).

## 1. Data model, and how Issues and To-Dos link to their sources

_To write._

## 2. API design

_To write._

## 3. Real-time transport, and how meeting state is owned and recovered

### Meeting state: `section` and `section_started_at`

The seed's meetings only record `started_at` and `ended_at`, which is enough for a meeting that's over. A live meeting also needs to know **where it is** and **how long it has been there**, so the `meetings` table gets two more columns:

- `section`: the current agenda item (`scorecard`, `ids` or `conclude`).
- `section_started_at`: when that item began, on the server clock.

**Why these two columns**

- **The server owns the timer.** The brief requires it. The database stores one fact, when the section started, and every browser computes elapsed time as `server_now − section_started_at`. All attendees see the same number, and nothing needs to be written every second.
- **Recovery for free.** Because state lives in Postgres and not in server memory or the facilitator's browser, a late join, a refresh, a reconnect (facilitator included) or a server restart reads the same two values and lands on the right section with the right time.
- **Over time without auto-advancing.** Elapsed time past the section's limit (5 / 60 / 10 min) is shown as "over time". The section only changes when the facilitator acts, which matches the brief.
- **Safe advancing.** "Next" is a conditional update: `UPDATE … SET section = :next WHERE section = :from`. A double-click or a stale browser updates 0 rows and gets a 409, so a section can't be skipped.

**Alternatives rejected**

| Option | Problem |
| --- | --- |
| Keep meeting state in server memory | Lost on restart; breaks with more than one server process |
| Store "seconds remaining" and decrement it | Needs a write every second; pausing and drift get complicated |
| Let the facilitator's browser run the timer | Clocks drift between browsers; the facilitator refreshing resets it |

**Tradeoffs**

- Only the current section's start is kept, so per-section durations of past meetings aren't recorded. A `meeting_sections` table (one row per section with start and end) would add that if it's ever needed.
- Browsers count up locally between events. Each browser corrects for its own clock using `server_now` from the server, so a wrong laptop clock doesn't show a wrong timer.

_Transport (SSE + REST) and fan-out (Postgres LISTEN/NOTIFY): to write._

## 4. Make it an Issue without duplicates under concurrent requests

_To write._

## 5. Keeping past meeting summaries unchanged after later edits

_To write._
