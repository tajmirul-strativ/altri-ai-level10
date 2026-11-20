"use client";

import { Check, ChevronRight, Clock, Flag } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useSectionTimer } from "@/hooks/use-section-timer";
import type { Meeting, Section } from "@/lib/api";
import { useMeetingActions } from "@/lib/queries";
import { formatDuration } from "@/lib/time";
import { cn } from "@/lib/utils";

import { AGENDA_TITLE } from "./agenda";

const ORDER: Section[] = ["scorecard", "ids", "conclude"];

type Props = { teamId: string; meeting: Meeting; receivedAt: number; isFacilitator: boolean };

export function MeetingHeader({ teamId, meeting, receivedAt, isFacilitator }: Props) {
  const actions = useMeetingActions(teamId, meeting.id);
  const current = meeting.agenda.find((a) => a.section === meeting.section)!;
  const timer = useSectionTimer(meeting, receivedAt, current.minutes);
  const currentIndex = ORDER.indexOf(meeting.section);
  const next = ORDER[currentIndex + 1];

  return (
    <section
      aria-label="Meeting controls"
      className="sticky top-14 z-20 -mx-4 border-b bg-background/95 px-4 py-3 backdrop-blur md:-mx-6 md:px-6"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <ol className="flex items-center gap-1 text-sm" aria-label="Agenda">
          {meeting.agenda.map((item, i) => {
            const done = i < currentIndex;
            const active = i === currentIndex;
            return (
              <li key={item.section} className="flex items-center gap-1">
                {i > 0 && <ChevronRight className="size-4 text-muted-foreground" aria-hidden />}
                <span
                  aria-current={active ? "step" : undefined}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1",
                    active && "border-primary bg-primary text-primary-foreground",
                    done && "text-muted-foreground",
                  )}
                >
                  {done && <Check className="size-3.5" aria-label="Done:" />}
                  {item.title}
                  <span className={cn("text-xs", active ? "opacity-80" : "text-muted-foreground")}>{item.minutes} min</span>
                </span>
              </li>
            );
          })}
        </ol>

        <div className="flex flex-1 items-center gap-3 lg:justify-center">
          <Clock className={cn("size-5", timer.isOver ? "text-off-track" : "text-muted-foreground")} aria-hidden />
          <div
            className={cn("text-3xl font-semibold tabular-nums", timer.isOver && "text-off-track")}
            role="timer"
            aria-label={`${AGENDA_TITLE[meeting.section]} time ${timer.isOver ? "over by" : "remaining"} ${formatDuration(
              timer.isOver ? timer.overSeconds : timer.remainingSeconds,
            )}`}
          >
            {timer.isOver ? `+${formatDuration(timer.overSeconds)}` : formatDuration(timer.remainingSeconds)}
          </div>
          <span className="text-sm text-muted-foreground">
            {timer.isOver ? (
              <Badge variant="outline" className="border-off-track/30 bg-off-track-subtle text-off-track">
                Over time
              </Badge>
            ) : (
              `left of ${current.minutes} min`
            )}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isFacilitator ? (
            <>
              <AlertDialog>
                <AlertDialogTrigger render={<Button variant={next ? "outline" : "default"} />}>
                  <Flag aria-hidden />
                  End meeting
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>End the meeting for everyone?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Ratings close and everyone sees the summary. This can&apos;t be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Keep going</AlertDialogCancel>
                    <AlertDialogAction onClick={() => actions.end.mutate()} disabled={actions.end.isPending}>
                      End meeting
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
              {next && (
                <Button
                  onClick={() => actions.advance.mutate(meeting.section)}
                  disabled={actions.advance.isPending}
                >
                  Next: {AGENDA_TITLE[next]}
                  <ChevronRight aria-hidden />
                </Button>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">{meeting.facilitator.name} is facilitating</p>
          )}
        </div>
      </div>
    </section>
  );
}
