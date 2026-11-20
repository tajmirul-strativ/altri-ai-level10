from fastapi import APIRouter
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.deps import ReadTeam, TeamContext, WriteTeam
from app.errors import conflict, forbidden, not_found
from app.events import publish
from app.models import Meeting, MeetingAttendee, MeetingRating
from app.schemas import AdvanceIn, MeetingOut, RatingIn, SummaryOut
from app.services.views import meeting_out
from app.summary import meeting_summary

router = APIRouter(prefix="/api/teams/{team_id}/meetings", tags=["meetings"])

NEXT_SECTION = {"scorecard": "ids", "ids": "conclude"}


def _meeting(ctx: TeamContext, meeting_id: str) -> Meeting:
    meeting = ctx.db.get(Meeting, meeting_id, populate_existing=True)
    if meeting is None or meeting.team_id != ctx.team.id:
        raise not_found("Meeting")
    return meeting


def _active(meeting: Meeting) -> Meeting:
    if meeting.ended_at is not None:
        raise conflict("meeting_ended", "This meeting has ended.")
    return meeting


def _facilitated_by_caller(ctx: TeamContext, meeting: Meeting) -> Meeting:
    if meeting.facilitator_id != ctx.user.id:
        raise forbidden("Only the facilitator can do this.")
    return meeting


def _state(ctx: TeamContext, meeting_id: str) -> MeetingOut:
    return meeting_out(ctx.db, _meeting(ctx, meeting_id), ctx.now)


def _changed(ctx: TeamContext, meeting_id: str) -> MeetingOut:
    """Commit, tell everyone watching the team, and return the new state."""
    publish(ctx.db, ctx.team.id, ["meeting"], meeting_id=meeting_id)
    ctx.db.commit()
    return _state(ctx, meeting_id)


@router.get("/active", summary="The team's running meeting, if any")
def get_active(ctx: ReadTeam) -> MeetingOut:
    meeting_id = ctx.db.scalar(
        select(Meeting.id).where(Meeting.team_id == ctx.team.id, Meeting.ended_at.is_(None))
    )
    if meeting_id is None:
        raise not_found("Active meeting")
    return _state(ctx, meeting_id)


@router.post("", status_code=201, summary="Start the meeting; the caller becomes facilitator")
def start_meeting(ctx: WriteTeam) -> MeetingOut:
    # One active meeting per team, guaranteed by a partial unique index. Concurrent starts
    # wait for the first one to commit, then skip and report it.
    meeting_id = ctx.db.execute(
        insert(Meeting)
        .values(
            team_id=ctx.team.id,
            facilitator_id=ctx.user.id,
            started_at=ctx.now,
            section="scorecard",
            section_started_at=ctx.now,
        )  # fmt: skip
        .on_conflict_do_nothing(index_elements=["team_id"], index_where=text("ended_at IS NULL"))
        .returning(Meeting.id)
    ).scalar()
    if meeting_id is None:
        active = ctx.db.scalar(
            select(Meeting.id).where(Meeting.team_id == ctx.team.id, Meeting.ended_at.is_(None))
        )
        raise conflict("meeting_active", "This team already has a meeting running.",
                       meeting_id=active)  # fmt: skip
    ctx.db.add(MeetingAttendee(meeting_id=meeting_id, user_id=ctx.user.id, joined_at=ctx.now))
    return _changed(ctx, meeting_id)


@router.get("/{meeting_id}", summary="Current meeting state (also used to recover after reconnect)")
def get_meeting(ctx: ReadTeam, meeting_id: str) -> MeetingOut:
    return _state(ctx, meeting_id)


@router.post("/{meeting_id}/join", summary="Join as an attendee (Observers included)")
def join_meeting(ctx: ReadTeam, meeting_id: str) -> MeetingOut:
    meeting = _active(_meeting(ctx, meeting_id))
    ctx.db.execute(
        insert(MeetingAttendee)
        .values(meeting_id=meeting.id, user_id=ctx.user.id, joined_at=ctx.now)
        .on_conflict_do_nothing()
    )
    return _changed(ctx, meeting.id)


@router.post("/{meeting_id}/advance", summary="Facilitator moves everyone to the next section")
def advance(ctx: WriteTeam, meeting_id: str, body: AdvanceIn) -> MeetingOut:
    meeting = _facilitated_by_caller(ctx, _active(_meeting(ctx, meeting_id)))
    next_section = NEXT_SECTION.get(body.from_section)
    if next_section is None:
        raise conflict("no_next_section", "Conclude is the last section; end the meeting instead.")
    # Conditional update: a double click or a stale browser updates nothing and gets a 409.
    moved = ctx.db.execute(
        update(Meeting)
        .where(
            Meeting.id == meeting.id,
            Meeting.section == body.from_section,
            Meeting.ended_at.is_(None),
        )  # fmt: skip
        .values(section=next_section, section_started_at=ctx.now)
        .returning(Meeting.id)
    ).scalar()
    if moved is None:
        raise conflict("stale_section", "The meeting has already moved on.")
    return _changed(ctx, meeting.id)


@router.post("/{meeting_id}/end", summary="Facilitator ends the meeting (any section)")
def end_meeting(ctx: WriteTeam, meeting_id: str) -> MeetingOut:
    meeting = _facilitated_by_caller(ctx, _meeting(ctx, meeting_id))
    ended = ctx.db.execute(
        update(Meeting)
        .where(Meeting.id == meeting.id, Meeting.ended_at.is_(None))
        .values(ended_at=ctx.now)
        .returning(Meeting.id)
    ).scalar()
    if ended is None:
        raise conflict("meeting_ended", "This meeting has already ended.")
    publish(ctx.db, ctx.team.id, ["scorecard", "issues", "todos"])
    return _changed(ctx, meeting.id)


@router.put("/{meeting_id}/rating", summary="Rate the meeting 1-10 in Conclude (can change)")
def rate_meeting(ctx: WriteTeam, meeting_id: str, body: RatingIn) -> MeetingOut:
    meeting = _active(_meeting(ctx, meeting_id))
    if ctx.db.get(MeetingAttendee, (meeting.id, ctx.user.id)) is None:
        raise conflict("not_attending", "Join the meeting before rating it.")
    if meeting.section != "conclude":
        raise conflict("not_conclude", "Ratings open in the Conclude section.")
    ctx.db.execute(
        insert(MeetingRating)
        .values(meeting_id=meeting.id, user_id=ctx.user.id, rating=body.rating)
        .on_conflict_do_update(
            index_elements=["meeting_id", "user_id"], set_={"rating": body.rating}
        )  # fmt: skip
    )
    return _changed(ctx, meeting.id)


@router.get("/{meeting_id}/summary", summary="Summary of an ended meeting")
def get_summary(ctx: ReadTeam, meeting_id: str) -> SummaryOut:
    meeting = _meeting(ctx, meeting_id)
    if meeting.ended_at is None:
        raise conflict("meeting_active", "The summary is available once the meeting ends.")
    s = meeting_summary(ctx.db, meeting, ctx.tz, ctx.now)
    return SummaryOut(
        meeting_id=s.meeting_id,
        scorecard_week=s.scorecard_week,
        measurable_status=s.measurable_status,
        issues_solved=s.issues_solved,
        todos_created=s.todos_created,
        attendee_ids=s.attendee_ids,
        rating=float(s.rating) if s.rating is not None else None,
    )
