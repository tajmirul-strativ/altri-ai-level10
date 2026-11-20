"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

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
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import type { Issue, UserOption } from "@/lib/api";
import { useAddTodo, useSolveIssue } from "@/lib/queries";
import { formatDay } from "@/lib/time";

type DialogProps = { teamId: string; issue: Issue; open: boolean; onOpenChange: (o: boolean) => void };

const solveSchema = z.object({ note: z.string().trim().min(1, "Write down what the team decided.").max(2000) });

export function SolveDialog({ teamId, issue, open, onOpenChange }: DialogProps) {
  const solve = useSolveIssue(teamId);
  const form = useForm({ resolver: zodResolver(solveSchema), defaultValues: { note: "" } });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Solve Issue</DialogTitle>
          <DialogDescription>{issue.title}</DialogDescription>
        </DialogHeader>
        <form
          id="solve-form"
          className="space-y-2"
          onSubmit={form.handleSubmit(({ note }) =>
            solve.mutate({ issueId: issue.id, note }, { onSuccess: () => onOpenChange(false) }),
          )}
        >
          <Label htmlFor="solve-note">Resolution note</Label>
          <Textarea
            id="solve-note"
            autoFocus
            rows={4}
            placeholder="What did the team decide?"
            aria-invalid={!!form.formState.errors.note}
            {...form.register("note")}
          />
          {form.formState.errors.note && (
            <p className="text-xs text-destructive">{form.formState.errors.note.message}</p>
          )}
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" form="solve-form" disabled={solve.isPending}>
            {solve.isPending ? "Solving…" : "Mark solved"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const todoSchema = z.object({
  title: z.string().trim().min(1, "Give the To-Do a title.").max(200),
  ownerId: z.string().min(1, "Choose who owns it."),
});

export function AddTodoDialog({
  teamId,
  issue,
  open,
  onOpenChange,
  owners,
  defaultOwnerId,
  dueDate,
}: DialogProps & { owners: UserOption[]; defaultOwnerId: string; dueDate: string }) {
  const addTodo = useAddTodo(teamId);
  const form = useForm({
    resolver: zodResolver(todoSchema),
    defaultValues: { title: "", ownerId: owners.some((o) => o.id === defaultOwnerId) ? defaultOwnerId : "" },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add To-Do</DialogTitle>
          <DialogDescription>For: {issue.title}</DialogDescription>
        </DialogHeader>
        <form
          id="todo-form"
          className="space-y-4"
          onSubmit={form.handleSubmit(({ title, ownerId }) =>
            addTodo.mutate(
              { issueId: issue.id, title, ownerId },
              {
                onSuccess: () => {
                  form.reset({ title: "", ownerId });
                  onOpenChange(false);
                },
              },
            ),
          )}
        >
          <div className="space-y-2">
            <Label htmlFor="todo-title">What needs to happen?</Label>
            <Input id="todo-title" autoFocus aria-invalid={!!form.formState.errors.title} {...form.register("title")} />
            {form.formState.errors.title && (
              <p className="text-xs text-destructive">{form.formState.errors.title.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="todo-owner">Owner</Label>
            <NativeSelect id="todo-owner" className="w-full" {...form.register("ownerId")}>
              <NativeSelectOption value="">Choose a person</NativeSelectOption>
              {owners.map((o) => (
                <NativeSelectOption key={o.id} value={o.id}>
                  {o.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            {form.formState.errors.ownerId && (
              <p className="text-xs text-destructive">{form.formState.errors.ownerId.message}</p>
            )}
          </div>
          <p className="text-sm text-muted-foreground">Due in 7 days: {formatDay(dueDate)}</p>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" form="todo-form" disabled={addTodo.isPending}>
            {addTodo.isPending ? "Adding…" : "Add To-Do"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
