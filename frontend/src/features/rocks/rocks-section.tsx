"use client";

import { AlertCircle, CheckCircle2, ChevronDown, Circle } from "lucide-react";

import { EmptyState, ErrorState, SectionSkeleton } from "@/components/page-states";
import { StatusBadge } from "@/components/status";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Progress } from "@/components/ui/progress";
import type { Rock } from "@/lib/api";
import { useRocks } from "@/lib/queries";
import { formatDay } from "@/lib/time";

export function RocksSection({ teamId }: { teamId: string }) {
  const rocks = useRocks(teamId);
  const quarter = rocks.data?.[0]?.quarter.replace("-", " ");

  return (
    <Card id="rocks">
      <CardHeader>
        <CardTitle className="text-lg">Rocks{quarter ? ` · ${quarter}` : ""}</CardTitle>
        <CardDescription>This quarter&apos;s goals. Expand a Rock to see its Milestones.</CardDescription>
      </CardHeader>
      <CardContent>
        {rocks.isPending ? (
          <SectionSkeleton rows={3} />
        ) : rocks.isError ? (
          <ErrorState error={rocks.error} />
        ) : rocks.data.length === 0 ? (
          <EmptyState>No Rocks this quarter.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {rocks.data.map((rock) => (
              <RockItem key={rock.id} rock={rock} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function RockItem({ rock }: { rock: Rock }) {
  return (
    <li className="rounded-lg border bg-background">
      <Collapsible>
        <CollapsibleTrigger className="group flex w-full flex-col gap-2 p-3 text-left hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1">
            <div className="font-medium">{rock.title}</div>
            <div className="text-xs text-muted-foreground">
              {rock.owner.name} · {rock.milestones.length} milestone{rock.milestones.length === 1 ? "" : "s"}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={rock.status} />
            <div className="flex w-32 items-center gap-2">
              <Progress value={rock.progress_percent} className="flex-1" aria-label={`${rock.progress_percent}% done`} />
              <span className="w-9 text-right text-xs tabular-nums">{rock.progress_percent}%</span>
            </div>
            <ChevronDown
              className="size-4 text-muted-foreground transition-transform group-data-panel-open:rotate-180"
              aria-hidden
            />
          </div>
        </CollapsibleTrigger>
        <CollapsibleContent>
          {rock.milestones.length === 0 ? (
            <p className="border-t px-3 py-2 text-sm text-muted-foreground">No milestones.</p>
          ) : (
            <ul className="divide-y border-t">
              {rock.milestones.map((m) => (
                <li key={m.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                  {m.done ? (
                    <CheckCircle2 className="size-4 text-on-track" aria-label="Done" />
                  ) : (
                    <Circle className="size-4 text-muted-foreground" aria-label="Not done" />
                  )}
                  <span className={m.done ? "flex-1 text-muted-foreground" : "flex-1"}>{m.title}</span>
                  {m.past_due && (
                    <Badge variant="outline" className="gap-1 border-off-track/30 bg-off-track-subtle text-off-track">
                      <AlertCircle className="size-3" aria-hidden />
                      Past due
                    </Badge>
                  )}
                  <span className="text-xs text-muted-foreground tabular-nums">Due {formatDay(m.due_date)}</span>
                </li>
              ))}
            </ul>
          )}
        </CollapsibleContent>
      </Collapsible>
    </li>
  );
}
