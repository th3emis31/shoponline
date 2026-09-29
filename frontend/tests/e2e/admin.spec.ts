import { expect, test } from "@playwright/test";

import type { Page } from "@playwright/test";

const TOKEN = "e2e-admin-token";
const OWNER = { email: "owner@e2e.test", password: "e2e owner password" };
const STAFF = { email: "staff@e2e.test", password: "e2e staff password" };

async function signIn(page: Page, who = OWNER) {
  await page.goto("/admin");
  await page.getByLabel("Email").fill(who.email);
  await page.getByLabel("Password").fill(who.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByTestId("whoami")).toContainText(who.email);
}

test("wrong password is rejected", async ({ page }) => {
  await page.goto("/admin");
  await page.getByLabel("Email").fill(OWNER.email);
  await page.getByLabel("Password").fill("not the password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Invalid email or password")).toBeVisible();
});

test("shared admin token is switched off once an owner account exists", async ({ page }) => {
  // The E2E backend has a personal owner account, so the shared token must no longer work.
  await page.goto("/admin");
  await page.getByRole("button", { name: /shared admin token/ }).click();
  await page.getByLabel(/Shared admin token/).fill(TOKEN);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Invalid admin token")).toBeVisible();
  await expect(page.getByTestId("whoami")).toHaveCount(0);
});

test("staff only see orders; sign out ends the session", async ({ page }) => {
  await signIn(page, STAFF);
  await expect(page.getByRole("button", { name: "Orders" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Products" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Audit" })).toHaveCount(0);
  const token = await page.evaluate(() => sessionStorage.getItem("novahaus.adminToken"));
  expect((await page.request.get("/admin-api/products", { headers: { "X-Admin-Token": token! } })).status()).toBe(403);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Email")).toBeVisible();
  expect((await page.request.get("/admin-api/me", { headers: { "X-Admin-Token": token! } })).status()).toBe(401);
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
  await expect(page.getByTestId("audit")).toContainText(OWNER.email); // who did it
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

test("owner manages the team from the browser", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Team", exact: true }).click();
  const team = page.getByTestId("team");
  const email = `helper-${Date.now()}@e2e.test`;
  await team.getByLabel("Email").fill(email);
  await team.getByLabel(/Password/).fill("helper password 42");
  await team.getByLabel("Role").selectOption("staff");
  await team.getByRole("button", { name: "Add" }).click();
  await expect(team.getByRole("status")).toContainText(`Added ${email}`);
  await expect(team.getByRole("row", { name: new RegExp(email) })).toContainText("staff");
  await expect(team.getByRole("row", { name: /owner@e2e.test/ })).toContainText("(you)");
});
