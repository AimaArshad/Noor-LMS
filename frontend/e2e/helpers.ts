import type { Page } from "@playwright/test";

// Guess at the User shape: if the app crashes after sign-in, adjust to src/types.
export const USER = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "student@example.com",
  full_name: "Test Student",
  name: "Test Student",
  role: "student",
  is_active: true,
};

const json = (body: unknown, status = 200) => ({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});

/** Mocks the API as a signed-in student. Later routes win, so the catch-all goes first. */
export async function mockSignedInApi(page: Page) {
  await page.route("**/api/v1/**", (route) => route.fulfill(json([])));
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill(json({ access_token: "test-access", refresh_token: "test-refresh", token_type: "bearer" })),
  );
  await page.route("**/api/v1/auth/me", (route) => route.fulfill(json(USER)));
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill(json({ access_token: "test-access", refresh_token: "test-refresh", token_type: "bearer" })),
  );
}

/** Signs in through the real login form. */
export async function signIn(page: Page) {
  await mockSignedInApi(page);
  await page.goto("/login");
  await page.getByLabel("Email").fill(USER.email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}
