import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";

import type { Rock, Status } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS = {
  on_track: { label: "On track", Icon: CheckCircle2, className: "text-on-track bg-on-track-subtle border-on-track/30" },
  off_track: { label: "Off track", Icon: XCircle, className: "text-off-track bg-off-track-subtle border-off-track/30" },
  pending: { label: "Pending", Icon: CircleDashed, className: "text-pending bg-pending-subtle border-pending/30" },
  complete: { label: "Complete", Icon: CheckCircle2, className: "text-on-track bg-on-track-subtle border-on-track/30" },
} as const;

export function statusStyle(status: Status | Rock["status"]) {
  return STATUS[status];
}

/** Status is always shown as icon + text, never color alone. */
export function StatusBadge({ status, className }: { status: Status | Rock["status"]; className?: string }) {
  const { label, Icon, className: tone } = STATUS[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        tone,
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {label}
    </span>
  );
}
