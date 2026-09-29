import { expect, test } from "@playwright/test";

const OWNER = { email: "owner@e2e.test", password: "e2e owner password" };

test("launch checklist shows 14 gates and records the owner's confirmation", async ({ page }) => {
  await page.goto("/admin");
  await page.getByLabel("Email", { exact: true }).fill(OWNER.email);
  await page.getByLabel("Password").fill(OWNER.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Launch checklist", exact: true }).click();
  await expect(page.getByTestId("launch-score")).toContainText("of 14");
  await expect(page.locator("[data-testid^=gate-]")).toHaveCount(14);
  const shipping = page.getByTestId("gate-shipping");
  await shipping.getByLabel("Evidence / note").fill("Carrier account opened; drop test done");
  await shipping.getByRole("button", { name: "I confirm this is done" }).click();
  await expect(page.getByTestId("gate-shipping")).toContainText("Confirmed by owner@e2e.test");
  await expect(page.getByTestId("gate-shipping")).toContainText("✅");
  // undo so the next run starts clean
  await page.getByTestId("gate-shipping").getByRole("button", { name: "Undo my confirmation" }).click();
  await expect(page.getByTestId("gate-shipping")).toContainText("⬜");
});
