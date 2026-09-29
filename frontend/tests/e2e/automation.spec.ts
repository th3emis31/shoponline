import { expect, test, type Page } from "@playwright/test";

const OWNER = { email: "owner@e2e.test", password: "e2e owner password" };

async function signIn(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("Email", { exact: true }).fill(OWNER.email);
  await page.getByLabel("Password").fill(OWNER.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByTestId("whoami")).toContainText(OWNER.email);
}

test("low stock -> reorder waits for approval -> purchase order -> received adds stock", async ({ page }) => {
  page.on("dialog", (d) => d.accept(""));
  await signIn(page);

  // Stock runs low (GBP 6 x 20 = GBP 120, above the GBP 100 automatic limit).
  await page.getByRole("button", { name: "Products", exact: true }).click();
  const mat = page.getByTestId("product-desk-mat");
  await mat.getByLabel("Stock").fill("3");
  await mat.getByRole("button", { name: "Save" }).click();
  await expect(mat.getByLabel("Stock")).toHaveValue("3");

  await page.getByRole("button", { name: "Automation", exact: true }).click();
  await expect(page.getByTestId("automation")).toContainText("Schedule is OFF");
  await page.getByTestId("job-low_stock").getByRole("button", { name: "Run now" }).click();
  await expect(page.getByTestId("job-low_stock")).toContainText("desk-mat (pending)");

  await page.getByRole("button", { name: "Approvals", exact: true }).click();
  const rec = page.getByTestId("approvals").locator(".panel", { hasText: "Reorder 20 × desk-mat" });
  await expect(rec).toContainText("above the automatic limit");
  await rec.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByTestId("approvals")).toContainText("Purchase order");

  await page.getByRole("button", { name: "Purchase orders", exact: true }).click();
  const row = page.getByTestId("purchase-orders").getByRole("row", { name: /desk-mat/ }).first();
  await expect(row).toContainText("ready to send");
  await row.getByRole("button", { name: "Mark sent" }).click();
  await expect(page.getByTestId("purchase-orders").getByRole("row", { name: /desk-mat/ }).first()).toContainText("sent");
  await page.getByTestId("purchase-orders").getByRole("row", { name: /desk-mat/ }).first()
    .getByRole("button", { name: "Mark received" }).click();
  await expect(page.getByTestId("purchase-orders").getByRole("row", { name: /desk-mat/ }).first()).toContainText("received");

  await page.getByRole("button", { name: "Products", exact: true }).click();
  await expect(page.getByTestId("product-desk-mat").getByLabel("Stock")).toHaveValue("23");
});

test("daily report can be generated on demand", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Automation", exact: true }).click();
  await page.getByTestId("job-daily_report").getByRole("button", { name: "Run now" }).click();
  await expect(page.getByTestId("report")).toContainText("NOVAHAUS daily report");
  await expect(page.getByTestId("report")).toContainText("Needs attention");
});
