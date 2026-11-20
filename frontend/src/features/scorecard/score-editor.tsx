"use client";

import { AlertTriangle, ArrowRight } from "lucide-react";
import { useState } from "react";

import { StatusBadge } from "@/components/status";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Cell, MeasurableRow } from "@/lib/api";
import { useMakeIssue, useSaveScore } from "@/lib/queries";
import { formatDay } from "@/lib/time";

import { formatGoal, formatValue } from "./format";

type Props = {
  teamId: string;
  measurable: MeasurableRow;
  cell: Cell;
  canWrite: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Edit one week's score; turn an off-track score into an Issue. */
export function ScoreEditor({ teamId, measurable, cell, canWrite, open, onOpenChange }: Props) {
  const [draft, setDraft] = useState(cell.value === null ? "" : String(cell.value));
  const save = useSaveScore(teamId);
  const makeIssue = useMakeIssue(teamId);
  const inputId = `score-${measurable.id}-${cell.week_start}`;

  const trimmed = draft.trim();
  const parsed = trimmed === "" ? null : Number(trimmed);
  const invalid = trimmed !== "" && !Number.isFinite(parsed);
  const unchanged = parsed === cell.value;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (invalid || unchanged) return;
    save.mutate(
      { measurableId: measurable.id, week: cell.week_start, value: parsed },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{measurable.name}</DialogTitle>
          <DialogDescription>
            Week of {formatDay(cell.week_start)} · Goal {formatGoal(measurable)} · Owner {measurable.owner.name}
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2 text-sm">
          Current: <span className="font-medium tabular-nums">{formatValue(cell.value, measurable.unit)}</span>
          <StatusBadge status={cell.status} />
        </div>

        {canWrite ? (
          <form onSubmit={submit} className="space-y-2" id={`${inputId}-form`}>
            <Label htmlFor={inputId}>Score{measurable.unit !== "count" ? ` (${measurable.unit})` : ""}</Label>
            <Input
              id={inputId}
              inputMode="decimal"
              autoFocus
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              aria-invalid={invalid}
              aria-describedby={`${inputId}-help`}
              className="tabular-nums"
            />
            <p id={`${inputId}-help`} className={invalid ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>
              {invalid ? "Enter a number, for example 12 or 3.5." : "Leave empty to clear the score."}
            </p>
          </form>
        ) : (
          <p className="text-sm text-muted-foreground">Observers can view scores but can&apos;t change them.</p>
        )}

        {cell.status === "off_track" && (
          <div className="flex items-start gap-3 rounded-lg border border-off-track/30 bg-off-track-subtle p-3 text-sm">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-off-track" aria-hidden />
            <div className="flex-1 space-y-2">
              <p>
                {cell.open_issue_id
                  ? "This number is already on the Issues list."
                  : "Off track. Add it to the Issues list so the team can solve it."}
              </p>
              {canWrite && (
                <Button
                  type="button"
                  size="sm"
                  variant={cell.open_issue_id ? "outline" : "default"}
                  disabled={makeIssue.isPending}
                  onClick={() =>
                    makeIssue.mutate(
                      { measurableId: measurable.id, week: cell.week_start },
                      { onSuccess: () => onOpenChange(false) },
                    )
                  }
                >
                  {cell.open_issue_id ? "Show on Issues list" : "Make it an Issue"}
                  <ArrowRight aria-hidden />
                </Button>
              )}
            </div>
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {canWrite ? "Cancel" : "Close"}
          </Button>
          {canWrite && (
            <Button type="submit" form={`${inputId}-form`} disabled={invalid || unchanged || save.isPending}>
              {save.isPending ? "Saving…" : "Save score"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
