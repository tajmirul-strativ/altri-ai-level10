"use client";

import { ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppHeader } from "@/components/app-header";
import { ErrorState, SectionSkeleton } from "@/components/page-states";
import { Button } from "@/components/ui/button";
import { useTeamEvents } from "@/hooks/use-team-events";
import { ApiError } from "@/lib/api";
import { useMe, useTeam } from "@/lib/queries";

/** Header + live updates for every page of a team; handles sign-in and access errors. */
export function TeamShell({ teamId, children }: { teamId: string; children: React.ReactNode }) {
  const router = useRouter();
  const me = useMe();
  const team = useTeam(teamId);
  const live = useTeamEvents(teamId);

  const unauthenticated =
    (me.error instanceof ApiError && me.error.status === 401) ||
    (team.error instanceof ApiError && team.error.status === 401);
  useEffect(() => {
    if (unauthenticated) router.replace("/login");
  }, [unauthenticated, router]);

  const forbidden = team.error instanceof ApiError && team.error.status === 403;

  return (
    <>
      <AppHeader teamId={teamId} live={live} />
      <main className="mx-auto w-full max-w-[1440px] px-4 py-6 md:px-6">
        {forbidden ? (
          <div className="mx-auto flex max-w-md flex-col items-center gap-3 py-16 text-center">
            <ShieldAlert className="size-8 text-muted-foreground" aria-hidden />
            <h1 className="text-lg font-semibold">You don&apos;t have access to this team</h1>
            <p className="text-sm text-muted-foreground">Pick one of your teams from the switcher above.</p>
            <Button render={<Link href="/" />}>Go to my team</Button>
          </div>
        ) : team.isError && !unauthenticated ? (
          <ErrorState error={team.error} />
        ) : team.isPending || me.isPending ? (
          <SectionSkeleton rows={8} />
        ) : (
          children
        )}
      </main>
    </>
  );
}
