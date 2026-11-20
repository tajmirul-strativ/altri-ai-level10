"use client";

import { Eye } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { IssuesSection } from "@/features/issues/issues-section";
import { MeetingBanner } from "@/features/meeting/meeting-banner";
import { RocksSection } from "@/features/rocks/rocks-section";
import { ScorecardSection } from "@/features/scorecard/scorecard-section";
import { TodosSection } from "@/features/todos/todos-section";
import { useTeam } from "@/lib/queries";
import { formatDay, formatDayWithWeekday } from "@/lib/time";

export function TeamPage({ teamId }: { teamId: string }) {
  const team = useTeam(teamId).data;
  if (!team) return null; // TeamShell shows loading and errors

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{team.name}</h1>
          <p className="text-sm text-muted-foreground">
            Today is {formatDayWithWeekday(team.today)} · this week started {formatDay(team.current_week)}
          </p>
        </div>
        <nav aria-label="Sections" className="flex gap-3 text-sm">
          {["scorecard", "issues", "todos", "rocks"].map((s) => (
            <a key={s} href={`#${s}`} className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">
              {s === "todos" ? "To-Dos" : s[0].toUpperCase() + s.slice(1)}
            </a>
          ))}
        </nav>
      </div>

      {!team.can_write && (
        <Alert>
          <Eye />
          <AlertDescription>You&apos;re viewing as an Observer: you can see everything and join meetings, but not make changes.</AlertDescription>
        </Alert>
      )}

      <MeetingBanner team={team} />
      <ScorecardSection teamId={team.id} canWrite={team.can_write} />
      <div className="grid gap-6 lg:grid-cols-2">
        <IssuesSection team={team} />
        <TodosSection team={team} />
      </div>
      <RocksSection teamId={team.id} />
    </div>
  );
}
