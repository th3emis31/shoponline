import { expect, test } from "@playwright/test";

test("illustrations are labelled, never presented as photos", async ({ page }) => {
  await page.goto("/products/monitor-riser");
  await expect(page.locator("figure.illustration figcaption").first()).toContainText("Illustration");
  await expect(page.getByText("published once measured on the approved sample")).toBeVisible();
});

test("launch waitlist needs an explicit tick and confirms", async ({ page }) => {
  await page.goto("/");
  const form = page.getByTestId("waitlist").first();
  await form.getByLabel("Email for launch news").fill(`e2e-${Date.now()}@example.com`);
  const consent = form.getByRole("checkbox");
  await expect(consent).not.toBeChecked(); // never pre-ticked
  await consent.check();
  await form.getByRole("button", { name: "Notify me" }).click();
  await expect(page.getByTestId("waitlist-done")).toContainText("on the list");
});

test("cart shows count, free-delivery progress and a set upsell that switches correctly", async ({ page }) => {
  await page.goto("/products/desk-mat");
  await page.getByRole("button", { name: "Add to cart" }).first().click();
  await expect(page.getByRole("status")).toContainText("Added");
  await expect(page.getByTestId("cart-count")).toHaveText("1");

  await page.goto("/cart");
  await expect(page.getByTestId("delivery-bar")).toContainText("£18.00 more for free UK delivery");
  const upsell = page.getByTestId("bundle-upsell");
  await expect(upsell).toContainText("save £9.00");
  await upsell.getByRole("button", { name: /Switch to the set/ }).click();
  await expect(page.getByTestId("totals")).toContainText("£75.00");
  await expect(page.getByTestId("totals")).toContainText("Free");
  await expect(page.getByTestId("bundle-upsell")).toHaveCount(0);
  await expect(page.getByRole("cell", { name: "Desk Reset Bundle (mat + cable tray + clips)", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: /^Felt \+ Vegan-Leather Desk Mat/ })).toHaveCount(0);
});
