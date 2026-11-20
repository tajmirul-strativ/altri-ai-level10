"""Request and response bodies. Requests forbid unknown fields; responses use UTC 'Z' times."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints

UtcDatetime = Annotated[
    datetime,
    PlainSerializer(lambda d: d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), return_type=str),
]
Number = Annotated[Decimal, PlainSerializer(float, return_type=float)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Section = Literal["scorecard", "ids", "conclude"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- people / auth -------------------------------------------------------------------------


class UserRef(BaseModel):
    id: str
    name: str


class UserOption(UserRef):
    role: str


class CompanyOut(BaseModel):
    id: str
    name: str
    timezone: str


class MeOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    company: CompanyOut


class LoginIn(Input):
    user_id: str = Field(min_length=1, max_length=64)


# --- teams ---------------------------------------------------------------------------------


class TeamRef(BaseModel):
    id: str
    name: str


class TeamOut(TeamRef):
    members: list[UserOption]
    can_write: bool
    today: date
    current_week: date
    last_closed_week: date


# --- scorecard -----------------------------------------------------------------------------


class GoalOut(BaseModel):
    type: str
    value: Number | None
    min: Number | None
    max: Number | None


class CellOut(BaseModel):
    week_start: date
    value: Number | None
    status: Literal["on_track", "off_track", "pending"]
    open_issue_id: str | None


class MeasurableRow(BaseModel):
    id: str
    name: str
    unit: str
    owner: UserRef
    goal: GoalOut
    cells: list[CellOut]


class ScorecardOut(BaseModel):
    weeks: list[date]
    current_week: date
    last_closed_week: date
    measurables: list[MeasurableRow]


class ScoreIn(Input):
    value: Annotated[Decimal, Field(max_digits=15, decimal_places=4, allow_inf_nan=False)]


# --- issues / to-dos -------------------------------------------------------------------------


class IssueSource(BaseModel):
    measurable_id: str
    measurable_name: str
    week_start: date


class IssueOut(BaseModel):
    id: str
    title: str
    owner: UserRef
    priority: int | None
    created_at: UtcDatetime
    solved_at: UtcDatetime | None
    resolution_note: str | None
    source: IssueSource | None


class IssueCreate(Input):
    title: Title
    priority: Annotated[int, Field(ge=1, le=5, strict=True)] | None = None


class IssuePriority(Input):
    priority: Annotated[int, Field(ge=1, le=5, strict=True)] | None


class IssueSolve(Input):
    note: Note


class IssueRef(BaseModel):
    id: str
    title: str


class TodoOut(BaseModel):
    id: str
    title: str
    owner: UserRef
    due_date: date
    done_at: UtcDatetime | None
    overdue: bool
    source_issue: IssueRef | None
    created_at: UtcDatetime


class TodoCreate(Input):
    title: Title
    owner_id: str = Field(min_length=1, max_length=64)


class TodoUpdate(Input):
    done: Annotated[bool, Field(strict=True)]


class CompletionOut(BaseModel):
    due: int
    done: int
    rate_percent: int
    meets_target: bool


class WeekCompletion(BaseModel):
    week_start: date
    completion: CompletionOut | None


class TodosOut(BaseModel):
    todos: list[TodoOut]
    last_closed_week: WeekCompletion


# --- rocks ---------------------------------------------------------------------------------


class MilestoneOut(BaseModel):
    id: str
    title: str
    due_date: date
    done: bool
    past_due: bool


class RockOut(BaseModel):
    id: str
    title: str
    owner: UserRef
    quarter: str
    status: Literal["on_track", "off_track", "complete"]
    progress_percent: int
    milestones: list[MilestoneOut]


# --- meetings ------------------------------------------------------------------------------


class AgendaItem(BaseModel):
    section: Section
    title: str
    minutes: int


class RatingOut(BaseModel):
    user_id: str
    rating: int


class MeetingOut(BaseModel):
    id: str
    team_id: str
    facilitator: UserRef
    started_at: UtcDatetime
    ended_at: UtcDatetime | None
    section: Section
    section_started_at: UtcDatetime
    server_now: UtcDatetime
    agenda: list[AgendaItem]
    attendees: list[UserOption]
    ratings: list[RatingOut]
    average_rating: float | None


class AdvanceIn(Input):
    from_section: Section


class RatingIn(Input):
    rating: Annotated[int, Field(ge=1, le=10, strict=True)]


class SummaryOut(BaseModel):
    meeting_id: str
    scorecard_week: date
    measurable_status: dict[str, Literal["on_track", "off_track", "pending"]]
    issues_solved: list[str]
    todos_created: list[str]
    attendee_ids: list[str]
    rating: float | None
