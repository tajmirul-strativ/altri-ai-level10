"use client";

/**
 * Server state lives in TanStack Query. Query keys are scoped by team so a live `change`
 * event can invalidate exactly what changed (see hooks/use-team-events.ts).
 */
import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  api,
  ApiError,
  type Cell,
  type Issue,
  type Me,
  type Meeting,
  type Rock,
  type Scorecard,
  type Section,
  type Summary,
  type Team,
  type TeamRef,
  type Todo,
  type Todos,
  type UserOption,
} from "./api";

export const keys = {
  me: ["me"] as const,
  users: ["users"] as const,
  teams: ["teams"] as const,
  team: (t: string) => ["team", t] as const,
  scorecard: (t: string) => ["team", t, "scorecard"] as const,
  issues: (t: string, status: "open" | "solved") => ["team", t, "issues", status] as const,
  todos: (t: string) => ["team", t, "todos"] as const,
  rocks: (t: string) => ["team", t, "rocks"] as const,
  activeMeeting: (t: string) => ["team", t, "meeting", "active"] as const,
  meeting: (t: string, m: string) => ["team", t, "meeting", m] as const,
  summary: (t: string, m: string) => ["team", t, "meeting", m, "summary"] as const,
};

/** Which query keys each live-event resource refreshes. */
export function keysForResource(teamId: string, resource: string): QueryKey[] {
  switch (resource) {
    case "scorecard":
      return [keys.scorecard(teamId)];
    case "issues":
      return [["team", teamId, "issues"], keys.scorecard(teamId)];
    case "todos":
      return [keys.todos(teamId)];
    case "meeting":
      return [["team", teamId, "meeting"]];
    default:
      return [["team", teamId]];
  }
}

const T = (teamId: string) => `/teams/${encodeURIComponent(teamId)}`;

// --- reads ---------------------------------------------------------------------------------

export const useMe = () =>
  useQuery({ queryKey: keys.me, queryFn: () => api<Me>("/auth/me"), retry: false });

export const useUsers = () =>
  useQuery({ queryKey: keys.users, queryFn: () => api<UserOption[]>("/auth/users") });

export const useTeams = () =>
  useQuery({ queryKey: keys.teams, queryFn: () => api<TeamRef[]>("/teams") });

export const useTeam = (teamId: string) =>
  useQuery({ queryKey: keys.team(teamId), queryFn: () => api<Team>(T(teamId)), retry: false });

export const useScorecard = (teamId: string) =>
  useQuery({ queryKey: keys.scorecard(teamId), queryFn: () => api<Scorecard>(`${T(teamId)}/scorecard`) });

export const useIssues = (teamId: string, status: "open" | "solved" = "open") =>
  useQuery({
    queryKey: keys.issues(teamId, status),
    queryFn: () => api<Issue[]>(`${T(teamId)}/issues?status=${status}`),
  });

export const useTodos = (teamId: string) =>
  useQuery({ queryKey: keys.todos(teamId), queryFn: () => api<Todos>(`${T(teamId)}/todos`) });

export const useRocks = (teamId: string) =>
  useQuery({ queryKey: keys.rocks(teamId), queryFn: () => api<Rock[]>(`${T(teamId)}/rocks`) });

export const useActiveMeeting = (teamId: string) =>
  useQuery({
    queryKey: keys.activeMeeting(teamId),
    queryFn: async () => {
      try {
        return await api<Meeting>(`${T(teamId)}/meetings/active`);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
  });

export const useMeeting = (teamId: string, meetingId: string) =>
  useQuery({
    queryKey: keys.meeting(teamId, meetingId),
    queryFn: () => api<Meeting>(`${T(teamId)}/meetings/${encodeURIComponent(meetingId)}`),
    retry: false,
  });

export const useSummary = (teamId: string, meetingId: string, enabled: boolean) =>
  useQuery({
    queryKey: keys.summary(teamId, meetingId),
    queryFn: () => api<Summary>(`${T(teamId)}/meetings/${encodeURIComponent(meetingId)}/summary`),
    enabled,
  });

// --- writes --------------------------------------------------------------------------------

function useTeamMutation<TVars, TResult>(
  teamId: string,
  fn: (vars: TVars) => Promise<TResult>,
  opts: { refresh: string[]; success?: string | ((r: TResult) => string) },
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (result) => {
      for (const r of opts.refresh) {
        for (const key of keysForResource(teamId, r)) qc.invalidateQueries({ queryKey: key });
      }
      const msg = typeof opts.success === "function" ? opts.success(result) : opts.success;
      if (msg) toast.success(msg);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Something went wrong."),
  });
}

export const useSaveScore = (teamId: string) =>
  useTeamMutation(
    teamId,
    (v: { measurableId: string; week: string; value: number | null }): Promise<Cell | void> =>
      v.value === null
        ? api<void>(`${T(teamId)}/measurables/${v.measurableId}/scores/${v.week}`, { method: "DELETE" })
        : api<Cell>(`${T(teamId)}/measurables/${v.measurableId}/scores/${v.week}`, {
            method: "PUT",
            body: { value: v.value },
          }),
    { refresh: ["scorecard"], success: "Score saved" },
  );

export const useMakeIssue = (teamId: string) =>
  useTeamMutation(
    teamId,
    (v: { measurableId: string; week: string }) =>
      api<Issue>(`${T(teamId)}/measurables/${v.measurableId}/scores/${v.week}/issue`, { method: "POST" }),
    { refresh: ["issues"], success: (i) => `Issue ready: ${i.title}` },
  );

export const useCreateIssue = (teamId: string) =>
  useTeamMutation(
    teamId,
    (v: { title: string; priority: number | null }) =>
      api<Issue>(`${T(teamId)}/issues`, { method: "POST", body: v }),
    { refresh: ["issues"], success: "Issue added" },
  );

export const useSetPriority = (teamId: string) =>
  useTeamMutation(
    teamId,
    (v: { issueId: string; priority: number | null }) =>
      api<Issue>(`${T(teamId)}/issues/${v.issueId}`, { method: "PATCH", body: { priority: v.priority } }),
    { refresh: ["issues"] },
  );

export const useSolveIssue = (teamId: string) =>
  useTeamMutation(
    teamId,
    (v: { issueId: string; note: string }) =>
      api<Issue>(`${T(teamId)}/issues/${v.issueId}/solve`, { method: "POST", body: { note: v.note } }),
    { refresh: ["issues"], success: "Issue solved" },
  );

export const useAddTodo = (teamId: string) =>
  useTeamMutation(
    teamId,
    (v: { issueId: string; title: string; ownerId: string }) =>
      api<Todo>(`${T(teamId)}/issues/${v.issueId}/todos`, {
        method: "POST",
        body: { title: v.title, owner_id: v.ownerId },
      }),
    { refresh: ["todos"], success: "To-Do added" },
  );

export const useToggleTodo = (teamId: string) =>
  useTeamMutation(
    teamId,
    (v: { todoId: string; done: boolean }) =>
      api<Todo>(`${T(teamId)}/todos/${v.todoId}`, { method: "PATCH", body: { done: v.done } }),
    { refresh: ["todos"] },
  );

const M = (teamId: string, meetingId: string) => `${T(teamId)}/meetings/${encodeURIComponent(meetingId)}`;

export function useMeetingActions(teamId: string, meetingId: string) {
  const qc = useQueryClient();
  const onSuccess = (m: Meeting) => {
    qc.setQueryData(keys.meeting(teamId, m.id), m);
    qc.invalidateQueries({ queryKey: keys.activeMeeting(teamId) });
  };
  const onError = (e: Error) => {
    toast.error(e.message);
    qc.invalidateQueries({ queryKey: keys.meeting(teamId, meetingId) });
  };
  return {
    join: useMutation({ mutationFn: () => api<Meeting>(`${M(teamId, meetingId)}/join`, { method: "POST" }), onSuccess, onError }),
    advance: useMutation({
      mutationFn: (from: Section) =>
        api<Meeting>(`${M(teamId, meetingId)}/advance`, { method: "POST", body: { from_section: from } }),
      onSuccess,
      onError,
    }),
    end: useMutation({ mutationFn: () => api<Meeting>(`${M(teamId, meetingId)}/end`, { method: "POST" }), onSuccess, onError }),
    rate: useMutation({
      mutationFn: (rating: number) =>
        api<Meeting>(`${M(teamId, meetingId)}/rating`, { method: "PUT", body: { rating } }),
      onSuccess,
      onError,
    }),
  };
}

export function useStartMeeting(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      try {
        return await api<Meeting>(`${T(teamId)}/meetings`, { method: "POST" });
      } catch (e) {
        // Someone started one a moment earlier: join theirs instead.
        if (e instanceof ApiError && e.code === "meeting_active" && typeof e.body.meeting_id === "string") {
          return api<Meeting>(`${M(teamId, e.body.meeting_id)}/join`, { method: "POST" });
        }
        throw e;
      }
    },
    onSuccess: (m) => {
      qc.setQueryData(keys.meeting(teamId, m.id), m);
      qc.invalidateQueries({ queryKey: keys.activeMeeting(teamId) });
    },
    onError: (e) => toast.error(e.message),
  });
}
