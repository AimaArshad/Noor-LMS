import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Fails on serious or critical WCAG 2.0/2.1 A and AA problems.
const PUBLIC_PAGES = [
  { name: "login", path: "/login" },
  { name: "register", path: "/register" },
];

for (const { name, path } of PUBLIC_PAGES) {
  test(`axe: ${name} page has no serious accessibility violations`, async ({ page }) => {
    await page.route("**/api/v1/**", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"Not authenticated"}' }),
    );
    await page.goto(path);
    await page.waitForLoadState("networkidle");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    const serious = results.violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => ({
        rule: v.id,
        impact: v.impact,
        help: v.help,
        elements: v.nodes.map((n) => n.target.join(" ")).slice(0, 5),
      }));
    expect(serious).toEqual([]);
  });
}
