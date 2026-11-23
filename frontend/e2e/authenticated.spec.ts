import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { signIn } from "./helpers";

test("signing in leaves the login page", async ({ page }) => {
  await signIn(page);
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.locator("body")).not.toBeEmpty();
});

for (const path of ["/classes", "/audiobooks"]) {
  test(`axe: signed-in ${path} has no serious violations`, async ({ page }) => {
    await signIn(page);
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const serious = results.violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => ({ rule: v.id, help: v.help, elements: v.nodes.map((n) => n.target.join(" ")).slice(0, 5) }));
    expect(serious).toEqual([]);
  });
}
