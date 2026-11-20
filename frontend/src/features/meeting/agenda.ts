import type { Section } from "@/lib/api";

export const AGENDA_TITLE: Record<Section, string> = {
  scorecard: "Scorecard",
  ids: "IDS",
  conclude: "Conclude",
};

export const SECTION_HINT: Record<Section, string> = {
  scorecard: "Review last week's numbers (highlighted). Turn off-track numbers into Issues.",
  ids: "Work the Issues list from the top: Identify, Discuss, Solve. Add To-Dos for follow-up.",
  conclude: "Recap the new To-Dos, then everyone rates the meeting from 1 to 10.",
};
