"use client";

import { AlertCircle, CheckCircle2, Link2, Target } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorState, SectionSkeleton } from "@/components/page-states";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Team, Todo, Todos } from "@/lib/api";
import { useMe, useTodos, useToggleTodo } from "@/lib/queries";
import { formatDay, formatTimestamp } from "@/lib/time";
import { cn } from "@/lib/utils";

export function TodosSection({ team }: { team: Team }) {
  const todos = useTodos(team.id);
  const [view, setView] = useState<"open" | "done">("open");
  const timeZone = useMe().data?.company.timezone ?? "UTC";

  const items = todos.data?.todos.filter((t) => (view === "open" ? !t.done_at : !!t.done_at)) ?? [];
  // Done list: most recently finished first.
  if (view === "done") items.sort((a, b) => (b.done_at ?? "").localeCompare(a.done_at ?? ""));

  return (
    <Card id="todos">
      <CardHeader>
        <CardTitle className="text-lg">To-Dos</CardTitle>
        <CardDescription>Weekly commitments, due 7 days after they&apos;re made.</CardDescription>
        <CardAction>
          <ToggleGroup
            value={[view]}
            onValueChange={(v) => v[0] && setView(v[0] as "open" | "done")}
            variant="outline"
            size="sm"
            aria-label="Show"
          >
            <ToggleGroupItem value="open">Open</ToggleGroupItem>
            <ToggleGroupItem value="done">Done</ToggleGroupItem>
          </ToggleGroup>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        {todos.isPending ? (
          <SectionSkeleton rows={4} />
        ) : todos.isError ? (
          <ErrorState error={todos.error} />
        ) : (
          <>
            <CompletionRate data={todos.data} />
            {items.length === 0 ? (
              <EmptyState>{view === "open" ? "Everything is done." : "Nothing finished yet."}</EmptyState>
            ) : (
              <ul className="space-y-2" aria-label={view === "open" ? "Open To-Dos" : "Done To-Dos"}>
                {items.map((t) => (
                  <TodoItem key={t.id} team={team} todo={t} timeZone={timeZone} />
                ))}
              </ul>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function CompletionRate({ data }: { data: Todos }) {
  const { week_start, completion } = data.last_closed_week;
  return (
    <div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3">
      <Target className="size-5 shrink-0 text-muted-foreground" aria-hidden />
      <div className="flex-1 text-sm">
        <div className="font-medium">Last week&apos;s completion (week of {formatDay(week_start)})</div>
        <div className="text-muted-foreground">
          {completion
            ? `${completion.done} of ${completion.due} done on time. Target 90%.`
            : "Nothing was due last week."}
        </div>
      </div>
      {completion && (
        <div className="text-right">
          <div className="text-2xl font-semibold tabular-nums">{completion.rate_percent}%</div>
          <Badge
            variant="outline"
            className={cn(
              completion.meets_target
                ? "border-on-track/30 bg-on-track-subtle text-on-track"
                : "border-off-track/30 bg-off-track-subtle text-off-track",
            )}
          >
            {completion.meets_target ? "Target met" : "Below target"}
          </Badge>
        </div>
      )}
    </div>
  );
}

export function TodoItem({
  team,
  todo,
  timeZone,
  showSource = true,
  isNew = false,
}: {
  team: Team;
  todo: Todo;
  timeZone: string;
  /** Hide the linked Issue when the list is already grouped by Issue. */
  showSource?: boolean;
  /** Marks a To-Do created in the current meeting. */
  isNew?: boolean;
}) {
  const toggle = useToggleTodo(team.id);
  const id = `todo-${todo.id}`;
  return (
    <li className={cn("flex items-start gap-3 rounded-lg border bg-background p-3", todo.overdue && "border-off-track/40")}>
      <Checkbox
        id={id}
        className="mt-0.5"
        checked={!!todo.done_at}
        disabled={!team.can_write || toggle.isPending}
        onCheckedChange={(checked) => toggle.mutate({ todoId: todo.id, done: checked === true })}
        aria-label={todo.done_at ? `Mark "${todo.title}" not done` : `Mark "${todo.title}" done`}
      />
      <div className="min-w-0 flex-1 space-y-1">
        <label htmlFor={id} className={cn("block font-medium", todo.done_at && "text-muted-foreground line-through")}>
          {todo.title}
        </label>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {isNew && <Badge className="h-5">New</Badge>}
          <span>{todo.owner.name}</span>
          <span className="tabular-nums">Due {formatDay(todo.due_date)}</span>
          {todo.done_at && (
            <span className="inline-flex items-center gap-1">
              <CheckCircle2 className="size-3 text-on-track" aria-hidden />
              Done {formatTimestamp(todo.done_at, timeZone)}
            </span>
          )}
          {todo.overdue && (
            <Badge variant="outline" className="gap-1 border-off-track/30 bg-off-track-subtle text-off-track">
              <AlertCircle className="size-3" aria-hidden />
              Overdue
            </Badge>
          )}
          {showSource && todo.source_issue && (
            <span className="inline-flex items-center gap-1">
              <Link2 className="size-3" aria-hidden />
              {todo.source_issue.title}
            </span>
          )}
        </div>
      </div>
    </li>
  );
}
