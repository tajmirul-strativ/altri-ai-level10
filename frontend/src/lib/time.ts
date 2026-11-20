/**
 * Display helpers. Timestamps arrive in UTC and are shown in company time (design.md §8),
 * because weeks, due dates and "overdue" are all defined in company time. Calendar dates
 * (due dates, week starts) are shown as-is, never converted.
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function parts(isoDate: string): { y: number; m: number; d: number } {
  const [y, m, d] = isoDate.split("-").map(Number);
  return { y, m, d };
}

/** "2026-11-02" -> "Nov 2" */
export function formatDay(isoDate: string): string {
  const { m, d } = parts(isoDate);
  return `${MONTHS[m - 1]} ${d}`;
}

/** "2026-11-02" -> "Mon, Nov 2" */
export function formatDayWithWeekday(isoDate: string): string {
  const { y, m, d } = parts(isoDate);
  const weekday = new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    weekday: "short",
    timeZone: "UTC",
  });
  return `${weekday}, ${formatDay(isoDate)}`;
}

/** "2026-11-11T15:00:00Z" -> "Nov 11, 9:00 AM CST" in the company time zone. */
export function formatTimestamp(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
    timeZoneName: "short",
  }).format(new Date(iso));
}

/** 125 -> "2:05", -5 -> "0:00" */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}
