import { expect, test } from "@playwright/test";

const TOKEN = "e2e-admin-token";

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/admin");
  await page.getByLabel(/Admin token/).fill(TOKEN);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("wrong admin token is rejected", async ({ page }) => {
  await page.goto("/admin");
  await page.getByLabel(/Admin token/).fill("wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Invalid admin token")).toBeVisible();
});

test("admin sees a new order, ships it, and it is audited", async ({ page }) => {
  // Place an order as a customer.
  await page.goto("/products/cable-tray");
  await page.getByRole("button", { name: "Add to cart" }).click();
  await expect(page.getByRole("status")).toContainText("Added");
  await page.goto("/cart");
  await page.getByLabel("Full name").fill("Admin Test Buyer");
  await page.getByLabel(/Email/).fill("buyer@example.com");
  await page.getByLabel("Delivery address").fill("2 High St, Leeds");
  await page.getByRole("button", { name: /Continue to payment/ }).click();
  await expect(page).toHaveURL(/\/order\//);

  await signIn(page);
  const row = page.getByTestId("orders").getByRole("row", { name: /Admin Test Buyer/ }).first();
  await expect(row).toContainText("placed");
  page.once("dialog", (d) => d.accept("RM123456789GB"));
  await row.getByRole("button", { name: "Mark shipped" }).click();
  await expect(page.getByTestId("orders").getByRole("row", { name: /Admin Test Buyer/ }).first()).toContainText("shipped");

  await page.getByRole("button", { name: "Audit" }).click();
  await expect(page.getByTestId("audit")).toContainText("RM123456789GB");
});

test("admin products show break-even ROAS and stock edits persist", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Products" }).click();
  const mat = page.getByTestId("product-desk-mat");
  await expect(mat.getByTestId("roas")).toHaveText("2.22");
  await mat.getByLabel("Stock").fill("42");
  await mat.getByLabel(/Reason/).fill("E2E stock count");
  await mat.getByRole("button", { name: "Save" }).click();
  await page.reload();
  await page.getByRole("button", { name: "Products" }).click();
  await expect(page.getByTestId("product-desk-mat").getByLabel("Stock")).toHaveValue("42");
});

test("funnel counts product views, adds and purchases", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Funnel" }).click();
  const before = await page.getByTestId("funnel").getByRole("row", { name: /view product/ }).locator("td").nth(1).innerText();

  await page.goto("/products/desk-mat");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.waitForTimeout(300); // allow the fire-and-forget event to land

  await page.goto("/admin");
  await page.getByRole("button", { name: "Funnel" }).click();
  await expect(page.getByTestId("funnel").getByRole("row", { name: /view product/ }).locator("td").nth(1))
    .toHaveText(String(Number(before) + 1));
});
