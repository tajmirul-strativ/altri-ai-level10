"use client";

import { Star } from "lucide-react";

import { EmptyState, SectionSkeleton } from "@/components/page-states";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { TodoItem } from "@/features/todos/todos-section";
import type { Me, Meeting, Team } from "@/lib/api";
import { useMeetingActions, useTodos } from "@/lib/queries";

/** To-Dos created since the meeting started (the IDS section's output). */
export function NewTodosCard({ team, meeting, me }: { team: Team; meeting: Meeting; me: Me }) {
  const todos = useTodos(team.id);
  const created = todos.data?.todos.filter((t) => t.created_at >= meeting.started_at) ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">New To-Dos from this meeting</CardTitle>
        <CardDescription>Read them out: who does what, by when.</CardDescription>
      </CardHeader>
      <CardContent>
        {todos.isPending ? (
          <SectionSkeleton rows={2} />
        ) : created.length === 0 ? (
          <EmptyState>No To-Dos were added in this meeting.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {created.map((t) => (
              <TodoItem key={t.id} team={team} todo={t} timeZone={me.company.timezone} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function RatingCard({ teamId, meeting, me }: { teamId: string; meeting: Meeting; me: Me }) {
  const { rate } = useMeetingActions(teamId, meeting.id);
  const mine = meeting.ratings.find((r) => r.user_id === me.id)?.rating;
  const names = Object.fromEntries(meeting.attendees.map((a) => [a.id, a.name]));
  const canRate = me.role !== "observer";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Rate this meeting</CardTitle>
        <CardDescription>
          {canRate
            ? "1 = poor, 10 = excellent. You can change your rating until the meeting ends."
            : "Observers don't rate meetings, but you can see the ratings."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {canRate && (
          <ToggleGroup
            value={mine ? [String(mine)] : []}
            onValueChange={(v) => v[0] && rate.mutate(Number(v[0]))}
            variant="outline"
            className="flex flex-wrap"
            aria-label="Your rating"
          >
            {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
              <ToggleGroupItem key={n} value={String(n)} aria-label={`Rate ${n} out of 10`} className="min-w-10 tabular-nums">
                {n}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        )}
        <div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3">
          <Star className="size-5 text-muted-foreground" aria-hidden />
          <div className="flex-1 text-sm">
            <div className="font-medium">Average rating</div>
            <div className="text-muted-foreground">
              {meeting.ratings.length} of {meeting.attendees.filter((a) => a.role !== "observer").length} rated
            </div>
          </div>
          <div className="text-2xl font-semibold tabular-nums" aria-live="polite">
            {meeting.average_rating?.toFixed(1) ?? "–"}
          </div>
        </div>
        {meeting.ratings.length > 0 && (
          <ul className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            {meeting.ratings.map((r) => (
              <li key={r.user_id} className="flex justify-between rounded-md border px-3 py-1.5">
                <span className="truncate">{names[r.user_id] ?? r.user_id}</span>
                <span className="font-medium tabular-nums">{r.rating}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
