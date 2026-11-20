"use client";

import { useEffect, useRef, useState } from "react";

import { EmptyState, ErrorState, SectionSkeleton } from "@/components/page-states";
import { statusStyle, StatusBadge } from "@/components/status";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Cell, MeasurableRow } from "@/lib/api";
import { useScorecard } from "@/lib/queries";
import { formatDay } from "@/lib/time";
import { cn } from "@/lib/utils";

import { formatGoal, formatValue } from "./format";
import { ScoreEditor } from "./score-editor";

type Props = {
  teamId: string;
  canWrite: boolean;
  /** In the meeting: the week under review gets highlighted. */
  focusWeek?: string;
  description?: string;
};

export function ScorecardSection({ teamId, canWrite, focusWeek, description }: Props) {
  const scorecard = useScorecard(teamId);
  const [editing, setEditing] = useState<{ m: MeasurableRow; cell: Cell } | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  // Show the most recent weeks first; older weeks are a scroll away.
  useEffect(() => {
    if (scorecard.data && scroller.current) scroller.current.scrollLeft = scroller.current.scrollWidth;
  }, [scorecard.data]);

  return (
    <Card id="scorecard">
      <CardHeader>
        <CardTitle className="text-lg">Scorecard</CardTitle>
        <CardDescription>
          {description ?? "Weekly numbers for the last 13 weeks. Select a cell to enter or change a score."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {scorecard.isPending ? (
          <SectionSkeleton rows={5} />
        ) : scorecard.isError ? (
          <ErrorState error={scorecard.error} />
        ) : scorecard.data.measurables.length === 0 ? (
          <EmptyState>This team has no Measurables yet.</EmptyState>
        ) : (
          <>
            <div ref={scroller} className="overflow-x-auto rounded-lg border">
              <table className="w-full border-collapse text-sm">
                <caption className="sr-only">Scorecard: Measurables by week</caption>
                <thead>
                  <tr className="bg-muted/60">
                    <th
                      scope="col"
                      className="sticky left-0 z-10 min-w-48 border-r bg-muted px-3 py-2 text-left text-xs font-medium text-muted-foreground"
                    >
                      Measurable
                    </th>
                    {scorecard.data.weeks.map((w) => (
                      <th
                        key={w}
                        scope="col"
                        className={cn(
                          "px-2 py-2 text-center text-xs font-medium whitespace-nowrap text-muted-foreground",
                          w === focusWeek && "bg-primary/10 text-foreground",
                        )}
                      >
                        {formatDay(w)}
                        {w === scorecard.data.current_week && <div className="font-normal">This week</div>}
                        {w === scorecard.data.last_closed_week && <div className="font-normal">Last week</div>}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {scorecard.data.measurables.map((m) => (
                    <tr key={m.id} className="border-t">
                      <th scope="row" className="sticky left-0 z-10 min-w-48 border-r bg-background px-3 py-2 text-left font-normal shadow-[2px_0_4px_-2px_rgb(0_0_0/0.08)]">
                        <div className="font-medium">{m.name}</div>
                        <div className="text-xs text-muted-foreground">
                          <span className="tabular-nums">Goal {formatGoal(m)}</span> · {m.owner.name}
                        </div>
                      </th>
                      {m.cells.map((cell) => {
                        const style = statusStyle(cell.status);
                        return (
                          <td
                            key={cell.week_start}
                            className={cn("p-1", cell.week_start === focusWeek && "bg-primary/10")}
                          >
                            <button
                              type="button"
                              onClick={() => setEditing({ m, cell })}
                              aria-label={`${m.name}, week of ${formatDay(cell.week_start)}: ${formatValue(
                                cell.value,
                                m.unit,
                              )}, ${style.label}${cell.open_issue_id ? ", on the Issues list" : ""}`}
                              className={cn(
                                "flex h-9 w-full min-w-16 items-center justify-center gap-1 rounded-md border px-2 tabular-nums transition-colors hover:ring-2 hover:ring-ring/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                                style.className,
                              )}
                            >
                              <style.Icon className="size-3.5 shrink-0" aria-hidden />
                              <span>{formatValue(cell.value, m.unit)}</span>
                              {cell.open_issue_id && (
                                <span className="size-1.5 rounded-full bg-current" title="On the Issues list" />
                              )}
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <StatusBadge status="on_track" />
              <StatusBadge status="off_track" />
              <StatusBadge status="pending" />
              <span>Pending: this week, not entered yet. A dot means the number is on the Issues list.</span>
            </div>
          </>
        )}
      </CardContent>
      {editing && (
        <ScoreEditor
          key={`${editing.m.id}-${editing.cell.week_start}`}
          teamId={teamId}
          measurable={editing.m}
          cell={editing.cell}
          canWrite={canWrite}
          open
          onOpenChange={(open) => !open && setEditing(null)}
        />
      )}
    </Card>
  );
}
