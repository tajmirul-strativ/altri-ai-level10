"""Initial schema: every table, constraint, partial index and role trigger (design.md §3).

Written as plain SQL so the exact database rules are easy to read and review.

Revision ID: 0001
Revises:
Create Date: 2026-11-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
-- ---------------------------------------------------------------------------------------
-- Company, users, teams
-- ---------------------------------------------------------------------------------------
CREATE TABLE companies (
    id        text PRIMARY KEY,
    name      text NOT NULL,
    timezone  text NOT NULL
);

CREATE TABLE users (
    id          text PRIMARY KEY,
    company_id  text NOT NULL REFERENCES companies (id),
    name        text NOT NULL,
    email       text NOT NULL,
    role        text NOT NULL,
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_role CHECK (role IN ('admin', 'team_member', 'observer'))
);

CREATE TABLE teams (
    id          text PRIMARY KEY,
    company_id  text NOT NULL REFERENCES companies (id),
    name        text NOT NULL
);

CREATE TABLE team_memberships (
    team_id  text NOT NULL REFERENCES teams (id) ON DELETE CASCADE,
    user_id  text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    PRIMARY KEY (team_id, user_id)
);
CREATE INDEX ix_team_memberships_user ON team_memberships (user_id);

-- ---------------------------------------------------------------------------------------
-- Measurables and weekly scores
-- ---------------------------------------------------------------------------------------
CREATE TABLE measurables (
    id          text PRIMARY KEY,
    team_id     text NOT NULL REFERENCES teams (id),
    name        text NOT NULL,
    owner_id    text NOT NULL,
    unit        text NOT NULL,
    goal_type   text NOT NULL,
    goal_value  numeric,
    goal_min    numeric,
    goal_max    numeric,
    CONSTRAINT uq_measurables_id_team UNIQUE (id, team_id),
    CONSTRAINT fk_measurables_owner_member FOREIGN KEY (team_id, owner_id)
        REFERENCES team_memberships (team_id, user_id),
    CONSTRAINT ck_measurables_goal_type
        CHECK (goal_type IN ('at_least', 'at_most', 'between', 'exactly')),
    CONSTRAINT ck_measurables_goal_shape CHECK (
        (goal_type = 'between'
            AND goal_value IS NULL AND goal_min IS NOT NULL AND goal_max IS NOT NULL
            AND goal_min <= goal_max)
        OR (goal_type IN ('at_least', 'at_most', 'exactly')
            AND goal_value IS NOT NULL AND goal_min IS NULL AND goal_max IS NULL)
    )
);
CREATE INDEX ix_measurables_team ON measurables (team_id);

CREATE TABLE scores (
    measurable_id  text NOT NULL REFERENCES measurables (id) ON DELETE CASCADE,
    week_start     date NOT NULL,
    value          numeric NOT NULL,
    updated_at     timestamptz,
    updated_by     text REFERENCES users (id),
    PRIMARY KEY (measurable_id, week_start),
    CONSTRAINT ck_scores_week_is_monday CHECK (extract(isodow FROM week_start) = 1)
);

-- ---------------------------------------------------------------------------------------
-- Rocks and milestones
-- ---------------------------------------------------------------------------------------
CREATE TABLE rocks (
    id        text PRIMARY KEY,
    team_id   text NOT NULL REFERENCES teams (id),
    title     text NOT NULL,
    owner_id  text NOT NULL,
    quarter   text NOT NULL,
    status    text NOT NULL,
    CONSTRAINT fk_rocks_owner_member FOREIGN KEY (team_id, owner_id)
        REFERENCES team_memberships (team_id, user_id),
    CONSTRAINT ck_rocks_quarter CHECK (quarter ~ '^[0-9]{4}-Q[1-4]$'),
    CONSTRAINT ck_rocks_status CHECK (status IN ('on_track', 'off_track', 'complete'))
);
CREATE INDEX ix_rocks_team_quarter ON rocks (team_id, quarter);

CREATE TABLE milestones (
    id        text PRIMARY KEY,
    rock_id   text NOT NULL REFERENCES rocks (id) ON DELETE CASCADE,
    title     text NOT NULL,
    due_date  date NOT NULL,
    done      boolean NOT NULL DEFAULT false
);
CREATE INDEX ix_milestones_rock ON milestones (rock_id);

-- ---------------------------------------------------------------------------------------
-- Issues. New ids continue the seed's style: i10, i11, ...
-- ---------------------------------------------------------------------------------------
CREATE SEQUENCE issues_id_seq;
CREATE TABLE issues (
    id                    text PRIMARY KEY DEFAULT 'i' || nextval('issues_id_seq'),
    team_id               text NOT NULL REFERENCES teams (id),
    title                 text NOT NULL,
    owner_id              text NOT NULL REFERENCES users (id),
    priority              smallint,
    created_at            timestamptz NOT NULL,
    solved_at             timestamptz,
    resolution_note       text,
    source_measurable_id  text,
    source_week_start     date,
    CONSTRAINT uq_issues_id_team UNIQUE (id, team_id),
    CONSTRAINT fk_issues_source_same_team FOREIGN KEY (source_measurable_id, team_id)
        REFERENCES measurables (id, team_id),
    CONSTRAINT ck_issues_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT ck_issues_priority CHECK (priority BETWEEN 1 AND 5),
    CONSTRAINT ck_issues_solved_has_note CHECK ((solved_at IS NULL) = (resolution_note IS NULL)),
    CONSTRAINT ck_issues_note_not_blank
        CHECK (resolution_note IS NULL OR btrim(resolution_note) <> ''),
    CONSTRAINT ck_issues_solved_after_created CHECK (solved_at IS NULL OR solved_at >= created_at),
    CONSTRAINT ck_issues_source_complete
        CHECK ((source_measurable_id IS NULL) = (source_week_start IS NULL)),
    CONSTRAINT ck_issues_source_week_is_monday
        CHECK (source_week_start IS NULL OR extract(isodow FROM source_week_start) = 1)
);
ALTER SEQUENCE issues_id_seq OWNED BY issues.id;
CREATE INDEX ix_issues_team_open ON issues (team_id) WHERE solved_at IS NULL;
-- No duplicate Issues: at most one unsolved Issue per Measurable and week.
-- Make it an Issue relies on this with INSERT ... ON CONFLICT (design.md §7).
CREATE UNIQUE INDEX uq_issues_open_per_cell
    ON issues (source_measurable_id, source_week_start) WHERE solved_at IS NULL;

-- ---------------------------------------------------------------------------------------
-- To-Dos. New ids: t42, t43, ...
-- ---------------------------------------------------------------------------------------
CREATE SEQUENCE todos_id_seq;
CREATE TABLE todos (
    id               text PRIMARY KEY DEFAULT 't' || nextval('todos_id_seq'),
    team_id          text NOT NULL REFERENCES teams (id),
    title            text NOT NULL,
    owner_id         text NOT NULL,
    due_date         date NOT NULL,
    done_at          timestamptz,
    source_issue_id  text,
    created_at       timestamptz NOT NULL,
    CONSTRAINT fk_todos_owner_member FOREIGN KEY (team_id, owner_id)
        REFERENCES team_memberships (team_id, user_id),
    CONSTRAINT fk_todos_source_same_team FOREIGN KEY (source_issue_id, team_id)
        REFERENCES issues (id, team_id),
    CONSTRAINT ck_todos_title_not_blank CHECK (btrim(title) <> '')
);
ALTER SEQUENCE todos_id_seq OWNED BY todos.id;
CREATE INDEX ix_todos_team_due ON todos (team_id, due_date);
CREATE INDEX ix_todos_source_issue ON todos (source_issue_id);

-- ---------------------------------------------------------------------------------------
-- Meetings. New ids: mt3, mt4, ...
-- ---------------------------------------------------------------------------------------
CREATE SEQUENCE meetings_id_seq;
CREATE TABLE meetings (
    id                  text PRIMARY KEY DEFAULT 'mt' || nextval('meetings_id_seq'),
    team_id             text NOT NULL REFERENCES teams (id),
    facilitator_id      text NOT NULL REFERENCES users (id),
    started_at          timestamptz NOT NULL,
    ended_at            timestamptz,
    section             text NOT NULL,
    section_started_at  timestamptz NOT NULL,
    CONSTRAINT ck_meetings_section CHECK (section IN ('scorecard', 'ids', 'conclude')),
    CONSTRAINT ck_meetings_ended_after_started CHECK (ended_at IS NULL OR ended_at >= started_at)
);
ALTER SEQUENCE meetings_id_seq OWNED BY meetings.id;
CREATE INDEX ix_meetings_team ON meetings (team_id);
-- One active meeting per team.
CREATE UNIQUE INDEX uq_meetings_one_active_per_team ON meetings (team_id) WHERE ended_at IS NULL;

CREATE TABLE meeting_attendees (
    meeting_id  text NOT NULL REFERENCES meetings (id) ON DELETE CASCADE,
    user_id     text NOT NULL REFERENCES users (id),
    joined_at   timestamptz NOT NULL,
    PRIMARY KEY (meeting_id, user_id)
);

CREATE TABLE meeting_ratings (
    meeting_id  text NOT NULL,
    user_id     text NOT NULL,
    rating      smallint NOT NULL,
    PRIMARY KEY (meeting_id, user_id),
    CONSTRAINT fk_meeting_ratings_attendee FOREIGN KEY (meeting_id, user_id)
        REFERENCES meeting_attendees (meeting_id, user_id) ON DELETE CASCADE,
    CONSTRAINT ck_meeting_ratings_range CHECK (rating BETWEEN 1 AND 10)
);

-- ---------------------------------------------------------------------------------------
-- Role rules a foreign key can't express (design.md §3):
--   * Observers can't own, facilitate or rate (they may attend).
--   * Issue owners, facilitators and attendees must be team members or Admins.
-- Membership-only columns (To-Do, Measurable, Rock owners) are covered by composite FKs,
-- so the trigger only checks the role there. Errors use SQLSTATE 23514 (check_violation).
-- ---------------------------------------------------------------------------------------
CREATE FUNCTION assert_team_participant(
    p_team_id text, p_user_id text, p_allow_observer boolean, p_check_membership boolean,
    p_what text
) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_role text;
BEGIN
    SELECT role INTO v_role FROM users WHERE id = p_user_id;
    IF v_role IS NULL THEN
        RETURN;  -- unknown user: the foreign key reports it
    END IF;
    IF v_role = 'observer' AND NOT p_allow_observer THEN
        RAISE EXCEPTION '% % is an Observer', p_what, p_user_id
            USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_participant_not_observer';
    END IF;
    IF p_check_membership AND v_role <> 'admin' AND NOT EXISTS (
        SELECT 1 FROM team_memberships WHERE team_id = p_team_id AND user_id = p_user_id
    ) THEN
        RAISE EXCEPTION '% % is neither a member of team % nor an Admin',
            p_what, p_user_id, p_team_id
            USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_participant_member_or_admin';
    END IF;
END;
$$;

CREATE FUNCTION trg_owner_not_observer() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM assert_team_participant(NEW.team_id, NEW.owner_id, false, false, 'owner');
    RETURN NEW;
END;
$$;

CREATE FUNCTION trg_issue_owner() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM assert_team_participant(NEW.team_id, NEW.owner_id, false, true, 'owner');
    RETURN NEW;
END;
$$;

CREATE FUNCTION trg_meeting_facilitator() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM assert_team_participant(NEW.team_id, NEW.facilitator_id, false, true, 'facilitator');
    RETURN NEW;
END;
$$;

CREATE FUNCTION trg_meeting_attendee() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM assert_team_participant(
        (SELECT team_id FROM meetings WHERE id = NEW.meeting_id), NEW.user_id, true, true,
        'attendee');
    RETURN NEW;
END;
$$;

CREATE FUNCTION trg_meeting_rater() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM assert_team_participant(
        (SELECT team_id FROM meetings WHERE id = NEW.meeting_id), NEW.user_id, false, false,
        'rater');
    RETURN NEW;
END;
$$;

CREATE TRIGGER measurables_owner BEFORE INSERT OR UPDATE OF owner_id, team_id ON measurables
    FOR EACH ROW EXECUTE FUNCTION trg_owner_not_observer();
CREATE TRIGGER rocks_owner BEFORE INSERT OR UPDATE OF owner_id, team_id ON rocks
    FOR EACH ROW EXECUTE FUNCTION trg_owner_not_observer();
CREATE TRIGGER todos_owner BEFORE INSERT OR UPDATE OF owner_id, team_id ON todos
    FOR EACH ROW EXECUTE FUNCTION trg_owner_not_observer();
CREATE TRIGGER issues_owner BEFORE INSERT OR UPDATE OF owner_id, team_id ON issues
    FOR EACH ROW EXECUTE FUNCTION trg_issue_owner();
CREATE TRIGGER meetings_facilitator
    BEFORE INSERT OR UPDATE OF facilitator_id, team_id ON meetings
    FOR EACH ROW EXECUTE FUNCTION trg_meeting_facilitator();
CREATE TRIGGER meeting_attendees_user BEFORE INSERT OR UPDATE ON meeting_attendees
    FOR EACH ROW EXECUTE FUNCTION trg_meeting_attendee();
CREATE TRIGGER meeting_ratings_user BEFORE INSERT OR UPDATE OF user_id ON meeting_ratings
    FOR EACH ROW EXECUTE FUNCTION trg_meeting_rater();
"""

DOWNGRADE = r"""
DROP TABLE IF EXISTS meeting_ratings, meeting_attendees, meetings, todos, issues, milestones,
    rocks, scores, measurables, team_memberships, teams, users, companies CASCADE;
DROP FUNCTION IF EXISTS trg_meeting_rater(), trg_meeting_attendee(), trg_meeting_facilitator(),
    trg_issue_owner(), trg_owner_not_observer(),
    assert_team_participant(text, text, boolean, boolean, text);
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
