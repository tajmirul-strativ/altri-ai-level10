import { TeamPage } from "@/features/team/team-page";

export default async function Page({ params }: PageProps<"/teams/[teamId]">) {
  const { teamId } = await params;
  return <TeamPage teamId={teamId} />;
}
