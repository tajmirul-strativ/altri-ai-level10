"use client";

import { Info } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";

import { ErrorState, SectionSkeleton } from "@/components/page-states";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { IssuesSection } from "@/features/issues/issues-section";
import { ScorecardSection } from "@/features/scorecard/scorecard-section";
import { ApiError } from "@/lib/api";
import { useMe, useMeeting, useMeetingActions, useTeam } from "@/lib/queries";

import { SECTION_HINT } from "./agenda";
import { NewTodosCard, RatingCard } from "./conclude-panel";
import { MeetingHeader } from "./meeting-header";
import { SummaryView } from "./summary-view";

export function MeetingView({ teamId, meetingId }: { teamId: string; meetingId: string }) {
  const team = useTeam(teamId).data;
  const me = useMe().data;
  const meetingQuery = useMeeting(teamId, meetingId);
  const meeting = meetingQuery.data;
  const { join } = useMeetingActions(teamId, meetingId);

  // Opening the meeting page joins it (once). Refreshes and late joins get the current state.
  const joined = useRef(false);
  useEffect(() => {
    if (!meeting || !me || joined.current || meeting.ended_at) return;
    joined.current = true;
    if (!meeting.attendees.some((a) => a.id === me.id)) join.mutate();
  }, [meeting, me, join]);

  if (meetingQuery.error instanceof ApiError && meetingQuery.error.status === 404) {
    return (
      <div className="mx-auto max-w-md space-y-3 py-16 text-center">
        <h1 className="text-lg font-semibold">Meeting not found</h1>
        <Button render={<Link href={`/teams/${teamId}`} />}>Back to team</Button>
      </div>
    );
  }
  if (meetingQuery.isError) return <ErrorState error={meetingQuery.error} />;
  if (!meeting || !team || !me) return <SectionSkeleton rows={8} />;
  if (meeting.ended_at) return <SummaryView team={team} meeting={meeting} timeZone={me.company.timezone} />;

  const isFacilitator = meeting.facilitator.id === me.id;

  return (
    <div className="space-y-6">
      <MeetingHeader
        teamId={teamId}
        meeting={meeting}
        receivedAt={meetingQuery.dataUpdatedAt}
        isFacilitator={isFacilitator}
      />

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{team.name} · Level 10 Meeting</h1>
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {meeting.attendees.length} attending: {meeting.attendees.map((a) => a.name).join(", ")}
        </p>
      </div>

      <Alert>
        <Info />
        <AlertDescription aria-live="polite">{SECTION_HINT[meeting.section]}</AlertDescription>
      </Alert>

      {meeting.section === "scorecard" && (
        <ScorecardSection
          teamId={teamId}
          canWrite={team.can_write}
          focusWeek={team.last_closed_week}
          description="Last week's column is highlighted. Select an off-track number to make it an Issue."
        />
      )}
      {meeting.section === "ids" && (
        <div className="grid gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2">
            <IssuesSection team={team} description="Work from the top. Solve with a note; add To-Dos for follow-up." />
          </div>
          <NewTodosCard team={team} meeting={meeting} me={me} />
        </div>
      )}
      {meeting.section === "conclude" && (
        <div className="grid gap-6 lg:grid-cols-2">
          <NewTodosCard team={team} meeting={meeting} me={me} />
          <RatingCard teamId={teamId} meeting={meeting} me={me} />
        </div>
      )}
    </div>
  );
}
