import { expect, test } from "@playwright/test";

test("home shows the collection without fabricated social proof", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Calm, organised desks");
  await expect(page.getByTestId("product-card").first()).toBeVisible();
  await expect(page.getByText("Preview site")).toBeVisible();
  const body = (await page.textContent("body")) ?? "";
  expect(body).not.toMatch(/only \d+ left|reviews?\b.*★|hurry/i);
});

test("full purchase flow: product → cart → checkout → order page", async ({ page }) => {
  await page.goto("/shop");
  await page.getByRole("link", { name: /Cable Clip Set/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Cable Clip Set");
  await page.getByRole("button", { name: "Add to cart" }).click();
  await expect(page.getByRole("status")).toContainText("Added");

  await page.goto("/cart");
  const totals = page.getByTestId("totals");
  await expect(totals).toContainText("£18.00");
  await expect(totals).toContainText("£3.95"); // delivery shown before payment
  await expect(totals).toContainText("£21.95");

  await page.getByLabel("Full name").fill("Jane Doe");
  await page.getByLabel("Email (for your receipt and tracking)").fill("jane@example.com");
  await page.getByLabel("Delivery address").fill("1 Main St, London");
  await page.getByRole("button", { name: /Continue to payment/ }).click();

  await expect(page).toHaveURL(/\/order\//);
  await expect(page.getByTestId("order-status")).toHaveText("Order placed");
  await expect(page.getByText("£21.95")).toBeVisible();

  // Cart is empty after checkout.
  await page.goto("/cart");
  await expect(page.getByText("Your cart is empty")).toBeVisible();
});

test("free delivery over threshold and remove item", async ({ page }) => {
  await page.goto("/products/desk-reset");
  await page.getByRole("button", { name: "Add to cart" }).click();
  await expect(page.getByRole("status")).toContainText("Added");
  await page.goto("/cart");
  await expect(page.getByTestId("totals")).toContainText("Free");
  await page.getByRole("button", { name: /Remove/ }).click();
  await expect(page.getByText("Your cart is empty")).toBeVisible();
});

test("order lookup needs the right email", async ({ page }) => {
  await page.goto("/track");
  await page.getByLabel("Order number").fill("does-not-exist");
  await page.getByLabel("Email", { exact: true }).fill("nobody@example.com");
  await page.getByRole("button", { name: "Track order" }).click();
  await expect(page.locator("p.error")).toContainText("couldn't find");
});

test("unknown product shows 404 page", async ({ page }) => {
  const res = await page.goto("/products/nope");
  expect(res?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
});

test("launch pages exist and are linked from the footer", async ({ page }) => {
  await page.goto("/");
  for (const name of ["About", "Contact", "FAQ", "Shipping", "Returns", "Privacy", "Terms", "Cookies"]) {
    const link = page.locator("footer").getByRole("link", { name, exact: true });
    await expect(link).toBeVisible();
    const href = await link.getAttribute("href");
    const res = await page.request.get(href!);
    expect(res.status(), href!).toBe(200);
  }
});

test("admin endpoints are not reachable through the public site", async ({ page }) => {
  const res = await page.request.get("/api/admin/products/desk-mat/economics");
  expect(res.status()).toBe(404);
});
