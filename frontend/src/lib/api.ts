/**
 * Typed client for the FastAPI backend. Types are generated from its OpenAPI schema:
 * `pnpm gen:api` (needs the API running on :8000).
 */
import type { components } from "./api-types";

type Schemas = components["schemas"];
export type Me = Schemas["MeOut"];
export type UserOption = Schemas["UserOption"];
export type TeamRef = Schemas["TeamRef"];
export type Team = Schemas["TeamOut"];
export type Scorecard = Schemas["ScorecardOut"];
export type MeasurableRow = Schemas["MeasurableRow"];
export type Cell = Schemas["CellOut"];
export type Issue = Schemas["IssueOut"];
export type Todo = Schemas["TodoOut"];
export type Todos = Schemas["TodosOut"];
export type Rock = Schemas["RockOut"];
export type Meeting = Schemas["MeetingOut"];
export type Summary = Schemas["SummaryOut"];
export type Section = Meeting["section"];
export type Status = Cell["status"];

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public body: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

function messageFrom(status: number, body: Record<string, unknown>): string {
  const detail = body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    // FastAPI validation errors: [{loc, msg}]
    const first = detail[0] as { msg?: string };
    return first.msg ?? "That doesn't look right. Please check and try again.";
  }
  return status >= 500 ? "Something went wrong on our side. Please try again." : "Request failed.";
}

export async function api<T>(
  path: string,
  init: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: init.method ?? "GET",
    headers: init.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    credentials: "same-origin",
    signal: init.signal,
  });
  if (response.status === 204) return undefined as T;
  const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok) {
    throw new ApiError(
      response.status,
      typeof body.code === "string" ? body.code : "error",
      messageFrom(response.status, body),
      body,
    );
  }
  return body as T;
}
