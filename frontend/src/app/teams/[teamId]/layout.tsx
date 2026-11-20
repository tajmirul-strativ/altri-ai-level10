import { TeamShell } from "@/features/team/team-shell";

export default async function TeamLayout({ children, params }: LayoutProps<"/teams/[teamId]">) {
  const { teamId } = await params;
  return <TeamShell teamId={teamId}>{children}</TeamShell>;
}
