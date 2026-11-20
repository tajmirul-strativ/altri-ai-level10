"use client";

import { ArrowRight, Play, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import type { Team } from "@/lib/api";
import { useActiveMeeting, useStartMeeting } from "@/lib/queries";

import { AGENDA_TITLE } from "./agenda";

/** Start the weekly meeting, or jump into the one already running. */
export function MeetingBanner({ team }: { team: Team }) {
  const router = useRouter();
  const active = useActiveMeeting(team.id);
  const start = useStartMeeting(team.id);

  if (active.isPending) return null;
  const meeting = active.data;

  return (
    <section
      aria-label="Level 10 Meeting"
      className="flex flex-col gap-3 rounded-xl border bg-background p-4 shadow-xs sm:flex-row sm:items-center"
    >
      <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
        <Users className="size-5" aria-hidden />
      </div>
      <div className="flex-1">
        {meeting ? (
          <>
            <p className="font-medium">
              <span className="mr-2 inline-block size-2 animate-pulse rounded-full bg-on-track align-middle" aria-hidden />
              Level 10 Meeting in progress
            </p>
            <p className="text-sm text-muted-foreground">
              Now in {AGENDA_TITLE[meeting.section]} · facilitated by {meeting.facilitator.name} ·{" "}
              {meeting.attendees.length} attending
            </p>
          </>
        ) : (
          <>
            <p className="font-medium">Weekly Level 10 Meeting</p>
            <p className="text-sm text-muted-foreground">
              {team.can_write
                ? "Scorecard (5 min), IDS (60 min), Conclude (10 min). Whoever starts it facilitates."
                : "No meeting is running. You can join as soon as someone starts one."}
            </p>
          </>
        )}
      </div>
      {meeting ? (
        <Button size="lg" render={<Link href={`/teams/${team.id}/meetings/${meeting.id}`} />}>
          Join meeting
          <ArrowRight aria-hidden />
        </Button>
      ) : team.can_write ? (
        <Button
          size="lg"
          disabled={start.isPending}
          onClick={() =>
            start.mutate(undefined, {
              onSuccess: (m) => router.push(`/teams/${team.id}/meetings/${m.id}`),
            })
          }
        >
          <Play aria-hidden />
          {start.isPending ? "Starting…" : "Start meeting"}
        </Button>
      ) : null}
    </section>
  );
}
