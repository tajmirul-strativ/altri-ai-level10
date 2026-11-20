import type { MeasurableRow } from "@/lib/api";

const num = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));

export function formatValue(value: number | null, unit: string): string {
  if (value === null) return "—";
  if (unit === "%") return `${value}%`;
  if (unit === "$k") return `$${value}k`;
  return String(value);
}

/** "≥ 10", "≤ 3%", "2–4 hours", "= 1" */
export function formatGoal(m: MeasurableRow): string {
  const { type, value, min, max } = m.goal;
  const unit = m.unit === "count" ? "" : m.unit === "%" || m.unit === "$k" ? "" : ` ${m.unit}`;
  const v = (x: number | null | undefined) => formatValue(x ?? null, m.unit === "count" ? "" : m.unit);
  switch (type) {
    case "at_least":
      return `≥ ${v(value)}${unit}`;
    case "at_most":
      return `≤ ${v(value)}${unit}`;
    case "exactly":
      return `= ${v(value)}${unit}`;
    case "between":
      return `${num(min)}–${num(max)}${unit}`;
    default:
      return "";
  }
}
