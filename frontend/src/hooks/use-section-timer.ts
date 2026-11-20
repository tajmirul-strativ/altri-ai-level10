"use client";

import { useEffect, useState } from "react";

import type { Meeting } from "@/lib/api";

/**
 * Elapsed time in the current meeting section, owned by the server (brief 2.5 "Sync").
 *
 * The server sends `section_started_at` and its own `server_now`. We measure how far this
 * browser's clock is from the server's at the moment the state arrived (`receivedAt`), then
 * count up locally, so a laptop with a wrong clock still shows the same timer as everyone else.
 */
export function useSectionTimer(meeting: Meeting | undefined, receivedAt: number, limitMinutes: number) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(id);
  }, []);

  if (!meeting) return { elapsedSeconds: 0, remainingSeconds: 0, overSeconds: 0, isOver: false };

  const offset = Date.parse(meeting.server_now) - receivedAt;
  const serverNow = meeting.ended_at ? Date.parse(meeting.ended_at) : now + offset;
  const elapsedSeconds = Math.max(0, (serverNow - Date.parse(meeting.section_started_at)) / 1000);
  const limit = limitMinutes * 60;
  return {
    elapsedSeconds,
    remainingSeconds: Math.max(0, limit - elapsedSeconds),
    overSeconds: Math.max(0, elapsedSeconds - limit),
    isOver: elapsedSeconds > limit,
  };
}
