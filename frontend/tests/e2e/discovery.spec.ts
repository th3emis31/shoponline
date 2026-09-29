import { expect, test } from "@playwright/test";

test("shop filters by room", async ({ page }) => {
  await page.goto("/shop");
  await expect(page.getByTestId("shop-grid").getByTestId("product-card")).toHaveCount(5);
  await page.getByRole("navigation", { name: "Filter by room" }).getByRole("link", { name: /Bedroom/ }).click();
  await expect(page).toHaveURL(/room=bedroom/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Bedroom");
  await expect(page.getByTestId("shop-grid").getByTestId("product-card")).toHaveCount(1);
  await page.goto("/shop?room=not-a-room");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Shop all");
});

test("buying guides are listed, readable and link to products", async ({ page }) => {
  await page.goto("/guides");
  await page.getByTestId("guide-list").getByRole("link").first().click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("cables");
  await expect(page.getByRole("heading", { name: "From our shop" })).toBeVisible();
  expect((await page.request.get("/guides/nope")).status()).toBe(404);
});

test("google shopping feed is valid XML and never lists products without a real photo", async ({ request }) => {
  const res = await request.get("/feed/google.xml");
  expect(res.status()).toBe(200);
  expect(res.headers()["content-type"]).toContain("xml");
  const body = await res.text();
  expect(body).toContain('xmlns:g="http://base.google.com/ns/1.0"');
  expect(body).not.toContain("<item>"); // no photos in the repo yet
  expect(body).toContain("real photo");
});
