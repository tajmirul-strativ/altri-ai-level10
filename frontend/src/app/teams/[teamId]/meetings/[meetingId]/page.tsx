import { MeetingView } from "@/features/meeting/meeting-view";

export default async function Page({ params }: PageProps<"/teams/[teamId]/meetings/[meetingId]">) {
  const { teamId, meetingId } = await params;
  return <MeetingView teamId={teamId} meetingId={meetingId} />;
}
