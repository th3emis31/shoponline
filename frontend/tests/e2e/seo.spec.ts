import { expect, test } from "@playwright/test";

test("preview site asks search engines not to index", async ({ page }) => {
  const robots = await page.request.get("/robots.txt");
  expect(robots.status()).toBe(200);
  expect(await robots.text()).toMatch(/Disallow: \//);
  await page.goto("/");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
});

test("sitemap lists pages and every product", async ({ page }) => {
  const res = await page.request.get("/sitemap.xml");
  expect(res.status()).toBe(200);
  const xml = await res.text();
  for (const path of ["/shop", "/faq", "/products/desk-mat", "/products/desk-reset"]) {
    expect(xml).toContain(path);
  }
});

test("product page has structured data and a canonical link", async ({ page }) => {
  await page.goto("/products/desk-mat");
  const raw = await page.locator('script[type="application/ld+json"]').textContent();
  const data = JSON.parse(raw!);
  expect(data["@type"]).toBe("Product");
  expect(data.offers.price).toBe("32.00");
  expect(data.offers.priceCurrency).toBe("GBP");
  expect(raw).not.toMatch(/aggregateRating/);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/products\/desk-mat$/);
  await expect(page).toHaveTitle(/Desk Mat/);
});
