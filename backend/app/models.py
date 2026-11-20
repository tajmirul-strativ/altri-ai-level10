"""ORM models. They mirror migrations/versions/0001_initial_schema.py exactly
(tests/test_models.py fails if they drift). The migration is the source of truth for
CHECK constraints and triggers; they are repeated here only where autogenerate compares them.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.rules import Goal

TZ_DATETIME = DateTime(timezone=True)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)  # admin | team_member | observer


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(Text)

    company: Mapped[Company] = relationship(lazy="joined")


class TeamMembership(Base):
    __tablename__ = "team_memberships"
    __table_args__ = (Index("ix_team_memberships_user", "user_id"),)

    team_id: Mapped[str] = mapped_column(
        Text, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )


class Measurable(Base):
    __tablename__ = "measurables"
    __table_args__ = (
        UniqueConstraint("id", "team_id", name="uq_measurables_id_team"),
        ForeignKeyConstraint(
            ["team_id", "owner_id"],
            ["team_memberships.team_id", "team_memberships.user_id"],
            name="fk_measurables_owner_member",
        ),
        Index("ix_measurables_team", "team_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    team_id: Mapped[str] = mapped_column(Text, ForeignKey("teams.id"))
    name: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    goal_type: Mapped[str] = mapped_column(Text)
    goal_value: Mapped[Decimal | None] = mapped_column(Numeric)
    goal_min: Mapped[Decimal | None] = mapped_column(Numeric)
    goal_max: Mapped[Decimal | None] = mapped_column(Numeric)

    @property
    def goal(self) -> Goal:
        return Goal(
            type=self.goal_type,  # type: ignore[arg-type]
            value=self.goal_value,
            min=self.goal_min,
            max=self.goal_max,
        )


class Score(Base):
    __tablename__ = "scores"

    measurable_id: Mapped[str] = mapped_column(
        Text, ForeignKey("measurables.id", ondelete="CASCADE"), primary_key=True
    )
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric)
    updated_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME)
    updated_by: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"))


class Rock(Base):
    __tablename__ = "rocks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "owner_id"],
            ["team_memberships.team_id", "team_memberships.user_id"],
            name="fk_rocks_owner_member",
        ),
        Index("ix_rocks_team_quarter", "team_id", "quarter"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    team_id: Mapped[str] = mapped_column(Text, ForeignKey("teams.id"))
    title: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(Text)
    quarter: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)  # seeded status: on_track | off_track | complete

    milestones: Mapped[list["Milestone"]] = relationship(
        order_by="Milestone.due_date", lazy="selectin"
    )


class Milestone(Base):
    __tablename__ = "milestones"
    __table_args__ = (Index("ix_milestones_rock", "rock_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    rock_id: Mapped[str] = mapped_column(Text, ForeignKey("rocks.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date)
    done: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        UniqueConstraint("id", "team_id", name="uq_issues_id_team"),
        ForeignKeyConstraint(
            ["source_measurable_id", "team_id"],
            ["measurables.id", "measurables.team_id"],
            name="fk_issues_source_same_team",
        ),
        Index("ix_issues_team_open", "team_id", postgresql_where=text("solved_at IS NULL")),
        Index(
            "uq_issues_open_per_cell",
            "source_measurable_id",
            "source_week_start",
            unique=True,
            postgresql_where=text("solved_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(
        Text, primary_key=True, server_default=text("'i' || nextval('issues_id_seq')")
    )
    team_id: Mapped[str] = mapped_column(Text, ForeignKey("teams.id"))
    title: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"))
    priority: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(TZ_DATETIME)
    solved_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    source_measurable_id: Mapped[str | None] = mapped_column(Text)
    source_week_start: Mapped[date | None] = mapped_column(Date)


class Todo(Base):
    __tablename__ = "todos"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "owner_id"],
            ["team_memberships.team_id", "team_memberships.user_id"],
            name="fk_todos_owner_member",
        ),
        ForeignKeyConstraint(
            ["source_issue_id", "team_id"],
            ["issues.id", "issues.team_id"],
            name="fk_todos_source_same_team",
        ),
        Index("ix_todos_team_due", "team_id", "due_date"),
        Index("ix_todos_source_issue", "source_issue_id"),
    )

    id: Mapped[str] = mapped_column(
        Text, primary_key=True, server_default=text("'t' || nextval('todos_id_seq')")
    )
    team_id: Mapped[str] = mapped_column(Text, ForeignKey("teams.id"))
    title: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date)
    done_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME)
    source_issue_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZ_DATETIME)


class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (
        Index("ix_meetings_team", "team_id"),
        Index(
            "uq_meetings_one_active_per_team",
            "team_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(
        Text, primary_key=True, server_default=text("'mt' || nextval('meetings_id_seq')")
    )
    team_id: Mapped[str] = mapped_column(Text, ForeignKey("teams.id"))
    facilitator_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(TZ_DATETIME)
    ended_at: Mapped[datetime | None] = mapped_column(TZ_DATETIME)
    section: Mapped[str] = mapped_column(Text)  # scorecard | ids | conclude
    section_started_at: Mapped[datetime] = mapped_column(TZ_DATETIME)

    attendees: Mapped[list["MeetingAttendee"]] = relationship(
        order_by="MeetingAttendee.user_id", lazy="selectin"
    )
    # Ratings reference attendees, not meetings directly, so the join is spelled out.
    ratings: Mapped[list["MeetingRating"]] = relationship(
        primaryjoin="Meeting.id == foreign(MeetingRating.meeting_id)",
        order_by="MeetingRating.user_id",
        lazy="selectin",
        viewonly=True,
    )


class MeetingAttendee(Base):
    __tablename__ = "meeting_attendees"

    meeting_id: Mapped[str] = mapped_column(
        Text, ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(TZ_DATETIME)


class MeetingRating(Base):
    __tablename__ = "meeting_ratings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meeting_id", "user_id"],
            ["meeting_attendees.meeting_id", "meeting_attendees.user_id"],
            ondelete="CASCADE",
            name="fk_meeting_ratings_attendee",
        ),
    )

    meeting_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    rating: Mapped[int] = mapped_column(SmallInteger)
