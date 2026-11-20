"use client";

import { ArrowLeft, CheckCircle2, ListTodo, Star, Users } from "lucide-react";
import Link from "next/link";

import { ErrorState, SectionSkeleton } from "@/components/page-states";
import { StatusBadge } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Meeting, Team } from "@/lib/api";
import { useIssues, useScorecard, useSummary, useTodos } from "@/lib/queries";
import { formatDay, formatTimestamp } from "@/lib/time";

export function SummaryView({ team, meeting, timeZone }: { team: Team; meeting: Meeting; timeZone: string }) {
  const summary = useSummary(team.id, meeting.id, true);
  const scorecard = useScorecard(team.id);
  const solved = useIssues(team.id, "solved");
  const todos = useTodos(team.id);

  if (summary.isPending) return <SectionSkeleton rows={6} />;
  if (summary.isError) return <ErrorState error={summary.error} />;
  const s = summary.data;

  const measurableName = Object.fromEntries(scorecard.data?.measurables.map((m) => [m.id, m.name]) ?? []);
  const issueTitle = Object.fromEntries(solved.data?.map((i) => [i.id, i.title]) ?? []);
  const todoById = Object.fromEntries(todos.data?.todos.map((t) => [t.id, t]) ?? []);
  const attendeeName = Object.fromEntries(meeting.attendees.map((a) => [a.id, a.name]));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Meeting summary</h1>
          <p className="text-sm text-muted-foreground">
            {team.name} · {formatTimestamp(meeting.started_at, timeZone)} to{" "}
            {meeting.ended_at ? formatTimestamp(meeting.ended_at, timeZone) : ""} · facilitated by{" "}
            {meeting.facilitator.name}
          </p>
        </div>
        <Button variant="outline" render={<Link href={`/teams/${team.id}`} />}>
          <ArrowLeft aria-hidden />
          Back to team
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Scorecard</CardTitle>
            <CardDescription>Week of {formatDay(s.scorecard_week)}</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="divide-y rounded-lg border">
              {Object.entries(s.measurable_status).map(([id, status]) => (
                <li key={id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                  <span>{measurableName[id] ?? id}</span>
                  <StatusBadge status={status} />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Star className="size-5" aria-hidden />
              Rating
            </CardTitle>
            <CardDescription>Average of everyone who rated</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-4xl font-semibold tabular-nums">{s.rating?.toFixed(1) ?? "No ratings"}</div>
            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                <Users className="size-4" aria-hidden />
                Attendees ({s.attendee_ids.length})
              </div>
              <p className="text-sm text-muted-foreground">
                {s.attendee_ids.map((id) => attendeeName[id] ?? id).join(", ")}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <CheckCircle2 className="size-5" aria-hidden />
              Issues solved ({s.issues_solved.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {s.issues_solved.length === 0 ? (
              <p className="text-sm text-muted-foreground">No issues were solved.</p>
            ) : (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {s.issues_solved.map((id) => (
                  <li key={id}>{issueTitle[id] ?? id}</li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ListTodo className="size-5" aria-hidden />
              To-Dos created ({s.todos_created.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {s.todos_created.length === 0 ? (
              <p className="text-sm text-muted-foreground">No To-Dos were created.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {s.todos_created.map((id) => {
                  const t = todoById[id];
                  return (
                    <li key={id} className="flex justify-between gap-3 rounded-md border px-3 py-1.5">
                      <span>{t?.title ?? id}</span>
                      {t && (
                        <span className="text-muted-foreground">
                          {t.owner.name} · due {formatDay(t.due_date)}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
