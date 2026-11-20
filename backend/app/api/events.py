from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.deps import ReadTeam
from app.realtime import Broker, get_broker, team_stream

router = APIRouter(prefix="/api/teams/{team_id}", tags=["live updates"])


@router.get(
    "/events",
    summary="Server-Sent Events: `change` events say which team data changed",
    response_class=StreamingResponse,
)
async def team_events(
    request: Request, ctx: ReadTeam, broker: Annotated[Broker, Depends(get_broker)]
) -> StreamingResponse:
    team_id = ctx.team.id
    # Release the database session now: the stream stays open for a long time.
    ctx.db.close()
    return StreamingResponse(
        team_stream(broker, team_id, request.is_disconnected, get_settings().sse_heartbeat_seconds),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
