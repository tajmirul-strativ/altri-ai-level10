import { expect, request, test, type Browser, type Page } from "@playwright/test";

/**
 * Brief Part 3: "One Playwright test with two browsers: the facilitator advances the agenda
 * and the second browser follows." Runs on the seeded Operations team (Harper Hill and Indy
 * Ito, both Team Members). Assertions don't depend on the clock.
 */

const TEAM = "team_ops";
const SYNC = { timeout: 3_000 }; // the brief asks for about a second; allow some CI slack

async function signedInPage(browser: Browser, name: string): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/login");
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await page.waitForURL(/\/teams\//);
  return page;
}

async function currentStep(page: Page) {
  return page.getByRole("list", { name: "Agenda" }).locator('[aria-current="step"]');
}

test.beforeEach(async ({ baseURL }) => {
  // Make the test repeatable: end a meeting a previous run may have left open.
  const api = await request.newContext({ baseURL });
  await api.post("/api/auth/login", { data: { user_id: "u8" } });
  const active = await api.get(`/api/teams/${TEAM}/meetings/active`);
  if (active.ok()) {
    const meeting = await active.json();
    await api.post("/api/auth/login", { data: { user_id: meeting.facilitator.id } });
    await api.post(`/api/teams/${TEAM}/meetings/${meeting.id}/end`);
  }
  await api.dispose();
});

test("facilitator advances the agenda and the second browser follows", async ({ browser }) => {
  const facilitator = await signedInPage(browser, "Harper Hill");
  const teammate = await signedInPage(browser, "Indy Ito");
  await facilitator.goto(`/teams/${TEAM}`);
  await teammate.goto(`/teams/${TEAM}`);

  // The teammate sees the meeting appear without reloading.
  await facilitator.getByRole("button", { name: "Start meeting" }).click();
  await facilitator.waitForURL(/\/meetings\/mt\d+/);
  await expect(teammate.getByText("Level 10 Meeting in progress")).toBeVisible(SYNC);
  await teammate.getByRole("link", { name: "Join meeting" }).click();

  // Both are on Scorecard; only the facilitator has the controls.
  await expect(await currentStep(facilitator)).toContainText("Scorecard");
  await expect(await currentStep(teammate)).toContainText("Scorecard");
  await expect(teammate.getByText("Harper Hill is facilitating")).toBeVisible();
  await expect(teammate.getByRole("button", { name: /^Next:/ })).toHaveCount(0);
  await expect(facilitator.getByText(/2 attending/)).toBeVisible(SYNC);

  // Facilitator advances; the teammate follows.
  await facilitator.getByRole("button", { name: "Next: IDS" }).click();
  await expect(await currentStep(teammate)).toContainText("IDS", SYNC);
  await expect(teammate.getByText(/Work the Issues list from the top/)).toBeVisible();

  await facilitator.getByRole("button", { name: "Next: Conclude" }).click();
  await expect(await currentStep(teammate)).toContainText("Conclude", SYNC);

  // A rating from the teammate shows up for the facilitator.
  await teammate.getByRole("button", { name: "Rate 8 out of 10" }).click();
  await expect(facilitator.getByText("8.0")).toBeVisible(SYNC);

  // Ending the meeting takes everyone to the summary.
  await facilitator.getByRole("button", { name: "End meeting" }).click();
  await facilitator.getByRole("alertdialog").getByRole("button", { name: "End meeting" }).click();
  await expect(teammate.getByRole("heading", { name: "Meeting summary" })).toBeVisible(SYNC);
  await expect(facilitator.getByRole("heading", { name: "Meeting summary" })).toBeVisible(SYNC);
});
