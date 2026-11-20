"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { BarChart3, CheckCircle2, ListPlus, ListTodo, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { EmptyState, ErrorState, SectionSkeleton } from "@/components/page-states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Issue, Team, Todo } from "@/lib/api";
import { useCreateIssue, useIssues, useMe, useSetPriority, useTodos } from "@/lib/queries";
import { formatDay, formatTimestamp } from "@/lib/time";

import { AddTodoDialog, SolveDialog } from "./issue-dialogs";

const PRIORITIES = [5, 4, 3, 2, 1];

const createSchema = z.object({
  title: z.string().trim().min(1, "Describe the issue in a few words.").max(200),
  priority: z.string(),
});

function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

type Props = { team: Team; description?: string };

export function IssuesSection({ team, description }: Props) {
  const [view, setView] = useState<"open" | "solved">("open");
  const open = useIssues(team.id, "open");
  const solved = useIssues(team.id, "solved");
  const current = view === "open" ? open : solved;
  const timeZone = useTimeZone();
  const todos = useTodos(team.id);
  const todosByIssue = useMemo(() => {
    const byIssue: Record<string, Todo[]> = {};
    for (const t of todos.data?.todos ?? []) {
      if (t.source_issue) (byIssue[t.source_issue.id] ??= []).push(t);
    }
    return byIssue;
  }, [todos.data]);

  return (
    <Card id="issues">
      <CardHeader>
        <CardTitle className="text-lg">Issues</CardTitle>
        <CardDescription>{description ?? "Problems to solve, highest priority first."}</CardDescription>
        <CardAction>
          <ToggleGroup
            value={[view]}
            onValueChange={(v) => v[0] && setView(v[0] as "open" | "solved")}
            variant="outline"
            size="sm"
            aria-label="Show"
          >
            <ToggleGroupItem value="open">Open{open.data ? ` (${open.data.length})` : ""}</ToggleGroupItem>
            <ToggleGroupItem value="solved">Solved</ToggleGroupItem>
          </ToggleGroup>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        {view === "open" && team.can_write && <NewIssueForm teamId={team.id} />}
        {current.isPending ? (
          <SectionSkeleton rows={4} />
        ) : current.isError ? (
          <ErrorState error={current.error} />
        ) : current.data.length === 0 ? (
          <EmptyState>{view === "open" ? "No open issues. Nice work." : "Nothing solved yet."}</EmptyState>
        ) : view === "open" ? (
          <ol className="space-y-2" aria-label="Open issues in priority order">
            {current.data.map((issue, index) => (
              <OpenIssue key={issue.id} team={team} issue={issue} rank={index + 1} todos={todosByIssue[issue.id] ?? []} timeZone={timeZone} />
            ))}
          </ol>
        ) : (
          <ul className="space-y-2" aria-label="Solved issues">
            {current.data.map((issue) => (
              <SolvedIssue key={issue.id} issue={issue} timeZone={timeZone} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function useTimeZone() {
  return useMe().data?.company.timezone ?? "UTC";
}

function NewIssueForm({ teamId }: { teamId: string }) {
  const create = useCreateIssue(teamId);
  const form = useForm({ resolver: zodResolver(createSchema), defaultValues: { title: "", priority: "" } });

  return (
    <form
      className="flex flex-col gap-2 rounded-lg border bg-muted/40 p-3 sm:flex-row sm:items-end"
      onSubmit={form.handleSubmit(({ title, priority }) =>
        create.mutate(
          { title, priority: priority ? Number(priority) : null },
          { onSuccess: () => form.reset() },
        ),
      )}
    >
      <div className="flex-1 space-y-1">
        <Label htmlFor="new-issue-title">New issue</Label>
        <Input
          id="new-issue-title"
          placeholder="e.g. Onboarding takes too long"
          aria-invalid={!!form.formState.errors.title}
          {...form.register("title")}
        />
        {form.formState.errors.title && (
          <p className="text-xs text-destructive">{form.formState.errors.title.message}</p>
        )}
      </div>
      <div className="space-y-1">
        <Label htmlFor="new-issue-priority">Priority</Label>
        <NativeSelect id="new-issue-priority" className="w-full sm:w-32" {...form.register("priority")}>
          <NativeSelectOption value="">None</NativeSelectOption>
          {PRIORITIES.map((p) => (
            <NativeSelectOption key={p} value={String(p)}>
              {p}
              {p === 5 ? " (highest)" : p === 1 ? " (lowest)" : ""}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </div>
      <Button type="submit" disabled={create.isPending}>
        <Plus aria-hidden />
        Add issue
      </Button>
    </form>
  );
}

function OpenIssue({
  team,
  issue,
  rank,
  todos,
  timeZone,
}: {
  team: Team;
  issue: Issue;
  rank: number;
  /** Every To-Do linked to this Issue, from any meeting. */
  todos: Todo[];
  timeZone: string;
}) {
  const setPriority = useSetPriority(team.id);
  const me = useMe();
  const doneCount = todos.filter((t) => t.done_at).length;
  const [dialog, setDialog] = useState<"solve" | "todo" | null>(null);
  const owners = useMemo(() => team.members.filter((m) => m.role !== "observer"), [team.members]);
  const selectId = `priority-${issue.id}`;

  return (
    <li className="rounded-lg border bg-background p-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-medium tabular-nums">
          {rank}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-medium">{issue.title}</p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>{issue.owner.name}</span>
            <span>Added {formatTimestamp(issue.created_at, timeZone)}</span>
            {issue.source && (
              <Badge variant="outline" className="gap-1">
                <BarChart3 className="size-3" aria-hidden />
                {issue.source.measurable_name} · week of {formatDay(issue.source.week_start)}
              </Badge>
            )}
            {todos.length > 0 && (
              <Badge variant="secondary" className="gap-1 tabular-nums">
                <ListTodo className="size-3" aria-hidden />
                {todos.length} To-Do{todos.length === 1 ? "" : "s"}
                {doneCount > 0 && ` · ${doneCount} done`}
              </Badge>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Label htmlFor={selectId} className="sr-only">
            Priority for {issue.title}
          </Label>
          {team.can_write ? (
            <NativeSelect
              id={selectId}
              size="sm"
              className="w-28"
              value={issue.priority === null ? "" : String(issue.priority)}
              disabled={setPriority.isPending}
              onChange={(e) =>
                setPriority.mutate({ issueId: issue.id, priority: e.target.value ? Number(e.target.value) : null })
              }
            >
              <NativeSelectOption value="">No priority</NativeSelectOption>
              {PRIORITIES.map((p) => (
                <NativeSelectOption key={p} value={String(p)}>
                  Priority {p}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          ) : (
            <Badge variant="secondary">{issue.priority ? `Priority ${issue.priority}` : "No priority"}</Badge>
          )}
          {team.can_write && (
            <>
              <Button size="sm" variant="outline" onClick={() => setDialog("todo")}>
                <ListPlus aria-hidden />
                To-Do
              </Button>
              <Button size="sm" onClick={() => setDialog("solve")}>
                <CheckCircle2 aria-hidden />
                Solve
              </Button>
            </>
          )}
        </div>
      </div>
      {dialog === "solve" && (
        <SolveDialog teamId={team.id} issue={issue} open onOpenChange={(o) => !o && setDialog(null)} />
      )}
      {dialog === "todo" && (
        <AddTodoDialog
          teamId={team.id}
          issue={issue}
          open
          onOpenChange={(o) => !o && setDialog(null)}
          owners={owners}
          defaultOwnerId={me.data?.id ?? ""}
          dueDate={addDays(team.today, 7)}
        />
      )}
    </li>
  );
}

function SolvedIssue({ issue, timeZone }: { issue: Issue; timeZone: string }) {
  return (
    <li className="rounded-lg border bg-background p-3">
      <div className="flex items-start gap-2">
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-on-track" aria-hidden />
        <div className="space-y-1">
          <p className="font-medium">{issue.title}</p>
          <p className="text-sm">{issue.resolution_note}</p>
          <p className="text-xs text-muted-foreground">
            Solved {issue.solved_at ? formatTimestamp(issue.solved_at, timeZone) : ""} · {issue.owner.name}
          </p>
        </div>
      </div>
    </li>
  );
}
