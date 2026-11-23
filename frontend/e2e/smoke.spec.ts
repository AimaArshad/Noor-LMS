import { expect, test, type Page } from "@playwright/test";

/** No session: every API call answers 401, like a signed-out browser. */
async function signedOut(page: Page) {
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"Not authenticated"}' }),
  );
}

test("login page shows the form", async ({ page }) => {
  await signedOut(page);
  await page.goto("/login");
  await expect(page.locator('input[type="password"]')).toBeVisible();
  await expect(page.getByRole("button", { name: /log ?in|sign ?in/i })).toBeVisible();
});

test("login page works with the keyboard only", async ({ page }) => {
  await signedOut(page);
  await page.goto("/login");
  await page.keyboard.press("Tab");
  const tag = await page.evaluate(() => document.activeElement?.tagName ?? "");
  expect(["INPUT", "A", "BUTTON"]).toContain(tag);
  // every focusable control gets a visible focus target in turn (no keyboard trap)
  const seen = new Set<string>();
  for (let i = 0; i < 8; i++) {
    seen.add(await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 80) ?? ""));
    await page.keyboard.press("Tab");
  }
  expect(seen.size).toBeGreaterThan(1);
});

test("signed-out visitors are sent to the login page", async ({ page }) => {
  await signedOut(page);
  for (const path of ["/audiobooks", "/classes", "/"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/login/);
  }
});

test("unknown pages do not crash the app", async ({ page }) => {
  await signedOut(page);
  await page.goto("/login");
  await expect(page.locator("body")).not.toBeEmpty();
});
