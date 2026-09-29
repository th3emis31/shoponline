import { expect, test } from "@playwright/test";

const OWNER = { email: "owner@e2e.test", password: "e2e owner password" };

test("order from an ad link is credited to the campaign with profit after ad cost", async ({ page }, info) => {
  const tag = `e2e-${info.project.name}`;
  await page.goto(`/products/cable-clips?utm_source=Facebook&utm_campaign=${tag}`);
  await page.getByRole("button", { name: "Add to cart" }).first().click();
  await expect(page.getByRole("status")).toContainText("Added");
  await page.goto("/cart");
  await page.getByLabel("Full name").fill("Ad Buyer");
  await page.getByLabel("Email (for your receipt and tracking)").fill("adbuyer@example.com");
  await page.getByLabel("Delivery address").fill("4 Ad Lane, Hull");
  await page.getByRole("button", { name: /Continue to payment/ }).click();
  await expect(page).toHaveURL(/\/order\//);

  await page.goto("/admin");
  await page.getByLabel("Email", { exact: true }).fill(OWNER.email);
  await page.getByLabel("Password").fill(OWNER.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Campaigns", exact: true }).click();
  const row = page.getByTestId(`campaign-facebook:${tag}`);
  await expect(row).toContainText("1"); // one order, one visit

  const today = new Date().toISOString().slice(0, 10);
  await page.getByLabel("Campaign tag (source:campaign)").fill(`facebook:${tag}`);
  await page.getByLabel("Date").fill(today);
  await page.getByLabel("Ad cost (£)").fill("5");
  await page.getByLabel("Clicks (optional)").fill("20");
  await page.getByRole("button", { name: "Save ad cost" }).click();
  await expect(page.getByTestId("campaigns").getByRole("status")).toContainText(`facebook:${tag}`);
  await expect(page.getByTestId(`campaign-facebook:${tag}`)).toContainText("£5.00");
  await expect(page.getByTestId(`campaign-facebook:${tag}`)).toContainText("£0.25"); // CPC
});
