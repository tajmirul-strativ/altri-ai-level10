"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { keysForResource } from "@/lib/queries";

export type LiveStatus = "connecting" | "live" | "reconnecting";

/**
 * Subscribes to the team's Server-Sent Events (design.md §7).
 *
 * - `change` events name what changed; the matching queries are refetched.
 * - Every (re)connect starts with `ready`. After a reconnect we refetch all team data, so
 *   anything missed while offline is picked up. The browser's EventSource retries by itself.
 */
export function useTeamEvents(teamId: string): LiveStatus {
  const qc = useQueryClient();
  const [status, setStatus] = useState<LiveStatus>("connecting");

  useEffect(() => {
    let connectedBefore = false;
    const source = new EventSource(`/api/teams/${encodeURIComponent(teamId)}/events`);

    source.addEventListener("ready", () => {
      if (connectedBefore) qc.invalidateQueries({ queryKey: ["team", teamId] });
      connectedBefore = true;
      setStatus("live");
    });
    source.addEventListener("change", (event) => {
      const data = JSON.parse((event as MessageEvent<string>).data) as { resources: string[] };
      for (const resource of data.resources) {
        for (const key of keysForResource(teamId, resource)) {
          qc.invalidateQueries({ queryKey: key });
        }
      }
    });
    source.onerror = () => setStatus("reconnecting");

    return () => source.close();
  }, [qc, teamId]);

  return status;
}
