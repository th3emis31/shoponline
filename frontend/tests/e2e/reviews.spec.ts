import { expect, test } from "@playwright/test";

const OWNER = { email: "owner@e2e.test", password: "e2e owner password" };

test("verified buyer reviews -> owner publishes -> shown on product page", async ({ page }, info) => {
  const product = info.project.name === "mobile" ? "monitor-riser" : "cable-tray";
  // no reviews: nothing is claimed
  await page.goto(`/products/${product}`);
  await expect(page.getByTestId("reviews")).toHaveCount(0);

  await page.getByRole("button", { name: "Add to cart" }).first().click();
  await expect(page.getByRole("status")).toContainText("Added");
  await page.goto("/cart");
  await page.getByLabel("Full name").fill("Rita Reviewer");
  await page.getByLabel("Email (for your receipt and tracking)").fill("rita@example.com");
  await page.getByLabel("Delivery address").fill("3 Low St, York");
  await page.getByRole("button", { name: /Continue to payment/ }).click();
  await expect(page).toHaveURL(/\/order\//);

  await page.getByTestId("write-review").click();
  await expect(page).toHaveURL(/\/review\//);
  await expect(page.getByText("Rita R.")).toBeVisible();
  const card = page.getByTestId(`review-${product}`);
  await card.getByLabel("4 stars").check();
  await card.getByLabel("Headline (optional)").fill("Solid and tidy");
  await card.getByLabel("Your review (optional)").fill("Does what it says. Assembly took two minutes.");
  await card.getByRole("button", { name: "Send review" }).click();
  await expect(card.getByRole("status")).toContainText("Thank you");

  // not public until checked
  await page.goto(`/products/${product}`);
  await expect(page.getByTestId("reviews")).toHaveCount(0);

  await page.goto("/admin");
  await page.getByLabel("Email", { exact: true }).fill(OWNER.email);
  await page.getByLabel("Password").fill(OWNER.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Reviews", exact: true }).click();
  const row = page.getByTestId("reviews-admin").getByRole("row", { name: /Solid and tidy/ }).first();
  await row.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByTestId("reviews-admin").getByRole("row", { name: /Solid and tidy/ }).first()).toContainText("published");

  await page.goto(`/products/${product}`);
  await expect(page.getByTestId("reviews")).toContainText("Solid and tidy");
  await expect(page.getByTestId("reviews")).toContainText("Verified buyer");
  const ld = await page.locator('script[type="application/ld+json"]').first().textContent();
  expect(ld).toContain("aggregateRating");
});

test("a forged review link is refused", async ({ page }) => {
  await page.goto("/review/not-an-order?token=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
  await expect(page.getByTestId("review-error")).toContainText("isn't valid");
});
