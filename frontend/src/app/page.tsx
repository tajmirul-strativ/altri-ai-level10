"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { SectionSkeleton } from "@/components/page-states";
import { useMe, useTeams } from "@/lib/queries";

/** Sends signed-in users to their first team, everyone else to the sign-in page. */
export default function Home() {
  const router = useRouter();
  const me = useMe();
  const teams = useTeams();

  useEffect(() => {
    if (me.isError) router.replace("/login");
    else if (teams.data?.[0]) router.replace(`/teams/${teams.data[0].id}`);
  }, [me.isError, teams.data, router]);

  return (
    <main className="mx-auto max-w-md p-8">
      {teams.data && teams.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">You aren&apos;t on any team yet.</p>
      ) : (
        <SectionSkeleton rows={2} />
      )}
    </main>
  );
}
