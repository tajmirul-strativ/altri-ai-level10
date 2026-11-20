"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ROLE_LABEL } from "@/components/app-header";
import { ErrorState, SectionSkeleton } from "@/components/page-states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useUsers } from "@/lib/queries";

/** Sign-in for the demo: pick one of the seeded users (sign-up is out of scope). */
export default function LoginPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const users = useUsers();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function signIn(userId: string) {
    setPending(userId);
    setError(null);
    try {
      await api("/auth/login", { method: "POST", body: { user_id: userId } });
      qc.clear();
      router.replace("/");
    } catch (e) {
      setError(e);
      setPending(null);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-4 py-10">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Sign in to Level 10</CardTitle>
          <CardDescription>Choose who you are. Each person sees the teams they belong to.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {error ? <ErrorState error={error} title="Couldn't sign in" /> : null}
          {users.isPending ? (
            <SectionSkeleton rows={6} />
          ) : users.isError ? (
            <ErrorState error={users.error} />
          ) : (
            <ul className="divide-y rounded-lg border" aria-label="Users">
              {users.data.map((u) => (
                <li key={u.id}>
                  <button
                    type="button"
                    onClick={() => signIn(u.id)}
                    disabled={pending !== null}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-none disabled:opacity-60"
                  >
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full border bg-muted text-sm font-medium">
                      {u.name
                        .split(" ")
                        .map((p) => p[0])
                        .join("")}
                    </span>
                    <span className="flex-1">
                      <span className="block font-medium">{u.name}</span>
                    </span>
                    <Badge variant={u.role === "admin" ? "default" : "secondary"}>{ROLE_LABEL[u.role]}</Badge>
                    <ChevronRight className="size-4 text-muted-foreground" aria-hidden />
                    <span className="sr-only">{pending === u.id ? "Signing in" : `Sign in as ${u.name}`}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
