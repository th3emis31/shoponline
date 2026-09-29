import { expect, test } from "@playwright/test";

const OWNER = { email: "owner@e2e.test", password: "e2e owner password" };

test("dropship: owner sets supplier -> customer buys -> supplier order with profit -> ordered", async ({ page }) => {
  page.on("dialog", (d) => d.accept("SUP-778"));
  await page.goto("/admin");
  await page.getByLabel("Email").fill(OWNER.email);
  await page.getByLabel("Password").fill(OWNER.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByTestId("whoami")).toContainText(OWNER.email);

  await page.getByRole("button", { name: "Products", exact: true }).click();
  const riser = page.getByTestId("product-monitor-riser");
  await riser.getByLabel("How it's fulfilled").selectOption("dropship");
  await riser.getByLabel("Supplier name").fill("Oak Supply Co");
  await riser.getByLabel("Supplier product link").fill("https://supplier.example/oak-riser");
  await riser.getByLabel(/Supplier price per unit/).fill("20.00");
  await riser.getByLabel("Delivery time shown to customers").fill("7-12 working days");
  await riser.getByRole("button", { name: "Save" }).click();
  await expect(page.getByTestId("product-monitor-riser").getByLabel("How it's fulfilled")).toHaveValue("dropship");

  // Customer side: delivery time is shown honestly; buying works with no own stock needed.
  await page.goto("/products/monitor-riser");
  await expect(page.getByTestId("delivery-estimate")).toContainText("7-12 working days");
  await page.getByRole("button", { name: "Add to cart" }).first().click();
  await expect(page.getByRole("status")).toContainText("Added");
  await page.goto("/cart");
  await page.getByLabel("Full name").fill("Drop Ship Buyer");
  await page.getByLabel(/Email/).fill("buyer2@example.com");
  await page.getByLabel("Delivery address").fill("9 Oak Road, Bristol");
  await page.getByRole("button", { name: /Continue to payment/ }).click();
  await expect(page).toHaveURL(/\/order\//);

  await page.goto("/admin");
  await page.getByRole("button", { name: "Supplier orders", exact: true }).click();
  const row = page.getByTestId("supplier-orders").getByRole("row", { name: /Drop Ship Buyer/ }).first();
  await expect(row).toContainText("9 Oak Road, Bristol");
  await expect(row).toContainText("Oak Supply Co");
  await expect(row).toContainText("£20.00"); // you pay
  await expect(row).toContainText("£59.00"); // customer paid
  await expect(row).toContainText("£28.28"); // 49.17 ex VAT - 20.00 - 0.89 Stripe
  await expect(row).toContainText("To order");
  await row.getByRole("button", { name: "Ordered" }).click();
  await expect(page.getByTestId("supplier-orders").getByRole("row", { name: /Drop Ship Buyer/ }).first()).toContainText("Ref SUP-778");
});
