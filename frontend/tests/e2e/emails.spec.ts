import { expect, test } from "@playwright/test";

const OWNER = { email: "owner@e2e.test", password: "e2e owner password" };

test("checkout opt-in is optional and unticked; newsletter + unsubscribe work", async ({ page }) => {
  await page.goto("/products/cable-clips");
  await page.getByRole("button", { name: "Add to cart" }).first().click();
  await expect(page.getByRole("status")).toContainText("Added");
  await page.goto("/cart");
  await expect(page.locator("main").getByLabel(/tips for small spaces/)).not.toBeChecked();

  // footer newsletter sign-up
  const email = `nl-${Date.now()}@example.com`;
  const nl = page.getByTestId("newsletter");
  await nl.getByLabel("Email for tips").fill(email);
  await nl.getByRole("checkbox").check();
  await nl.getByRole("button", { name: "Sign up" }).click();
  await expect(page.getByTestId("newsletter-done")).toContainText("welcome email");

  // owner sees the welcome email in the outbox (test mode, not sent)
  await page.goto("/admin");
  await page.getByLabel("Email", { exact: true }).fill(OWNER.email);
  await page.getByLabel("Password").fill(OWNER.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Emails", exact: true }).click();
  // the whole 5-step welcome series is queued; step 1 is the welcome itself
  const rows = page.getByTestId("emails").getByRole("row", { name: new RegExp(email) });
  await expect(rows).toHaveCount(5);
  await expect(rows.filter({ hasText: "Welcome to NOVAHAUS" })).toHaveCount(1);
  await expect(page.getByTestId("emails")).toContainText("Test mode");

  // unsubscribe with a bad token is refused politely
  await page.goto("/unsubscribe?token=not-a-real-token-123");
  await expect(page.getByTestId("unsubscribe-result")).toContainText("isn't valid");
});
