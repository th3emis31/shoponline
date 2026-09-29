import { expect, test } from "@playwright/test";

const OWNER = { email: "owner@e2e.test", password: "e2e owner password" };

test("owner asks an assistant, sees labelled advice and approves it into the decision log", async ({ page }) => {
  await page.goto("/admin");
  await page.getByLabel("Email", { exact: true }).fill(OWNER.email);
  await page.getByLabel("Password").fill(OWNER.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "AI assistants", exact: true }).click();
  await expect(page.getByTestId("ai")).toContainText("Built-in rules");
  await page.getByLabel("Assistant").selectOption("product");
  await page.getByLabel(/^Product/).selectOption("desk-mat");
  await page.getByRole("button", { name: "Ask the assistant" }).click();
  const task = page.locator("[data-testid^=ai-task-]").first();
  await expect(task).toContainText("FACT:");
  await expect(task).toContainText("margin gate");
  page.once("dialog", (d) => d.accept("Looks right"));
  await task.getByRole("button", { name: "Approve" }).click();
  await expect(page.locator("[data-testid^=ai-task-]").first()).toContainText("approved");
  await expect(page.getByTestId("ai").getByRole("table")).toContainText("Looks right");
});
