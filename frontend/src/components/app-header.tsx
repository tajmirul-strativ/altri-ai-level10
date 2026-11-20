"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CircleUserRound, LogOut, Wifi, WifiOff } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { LiveStatus } from "@/hooks/use-team-events";
import { api } from "@/lib/api";
import { useMe, useTeams } from "@/lib/queries";

export const ROLE_LABEL: Record<string, string> = {
  admin: "Admin",
  team_member: "Team Member",
  observer: "Observer",
};

export function AppHeader({ teamId, live }: { teamId: string; live: LiveStatus }) {
  const router = useRouter();
  const qc = useQueryClient();
  const me = useMe();
  const teams = useTeams();

  async function signOut() {
    await api("/auth/logout", { method: "POST" });
    qc.clear();
    router.replace("/login");
  }

  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/80">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-3 px-4 md:px-6">
        <Link href={`/teams/${teamId}`} className="font-semibold tracking-tight whitespace-nowrap">
          Level 10
        </Link>

        <label className="sr-only" htmlFor="team-switcher">
          Team
        </label>
        <NativeSelect
          id="team-switcher"
          className="w-40 sm:w-48"
          value={teamId}
          onChange={(e) => router.push(`/teams/${e.target.value}`)}
          disabled={!teams.data}
        >
          {(teams.data ?? [{ id: teamId, name: "…" }]).map((t) => (
            <NativeSelectOption key={t.id} value={t.id}>
              {t.name}
            </NativeSelectOption>
          ))}
        </NativeSelect>

        <div className="ml-auto flex items-center gap-2">
          <Tooltip>
            <TooltipTrigger
              render={<span />}
              className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex"
            >
              {live === "live" ? (
                <Wifi className="size-4 text-on-track" aria-hidden />
              ) : (
                <WifiOff className="size-4 text-off-track" aria-hidden />
              )}
              {live === "live" ? "Live" : live === "connecting" ? "Connecting…" : "Reconnecting…"}
            </TooltipTrigger>
            <TooltipContent>
              {live === "live"
                ? "Changes from teammates appear automatically."
                : "Trying to reconnect. Your screen will catch up automatically."}
            </TooltipContent>
          </Tooltip>

          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="ghost" className="gap-2" />}>
              <CircleUserRound className="size-5" aria-hidden />
              <span className="hidden max-w-36 truncate sm:inline">{me.data?.name ?? "Account"}</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuGroup>
                <DropdownMenuLabel>
                  <div className="font-medium text-foreground">{me.data?.name}</div>
                  <div className="text-xs font-normal">{me.data?.email}</div>
                  {me.data && (
                    <Badge variant="secondary" className="mt-1">
                      {ROLE_LABEL[me.data.role]}
                    </Badge>
                  )}
                </DropdownMenuLabel>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={signOut}>
                <LogOut aria-hidden />
                Switch user
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
