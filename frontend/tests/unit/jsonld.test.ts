import { describe, expect, it } from "vitest";
import { jsonLdScript, productJsonLd } from "@/lib/jsonld";

const mat = { id: "desk-mat", name: "Desk Mat", price: 3200, is_bundle: false, in_stock: true };

describe("productJsonLd", () => {
  it("describes the product offer in GBP with no invented ratings", () => {
    const d = productJsonLd(mat);
    expect(d["@type"]).toBe("Product");
    expect(d.offers).toMatchObject({ price: "32.00", priceCurrency: "GBP", availability: "https://schema.org/InStock" });
    expect(JSON.stringify(d)).not.toMatch(/aggregateRating|review/i);
  });
  it("adds no rating while there are zero published reviews", () => {
    const d = productJsonLd(mat, { count: 0, average: null, reviews: [] });
    expect(JSON.stringify(d)).not.toMatch(/aggregateRating|review/i);
  });
  it("adds rating only from real published reviews", () => {
    const d = productJsonLd(mat, {
      count: 2, average: 4.5,
      reviews: [{ id: 1, rating: 5, title: "Great", body: "Tidy desk", name: "Jane D.", date: "2026-09-01", verified: true }],
    }) as Record<string, unknown>;
    expect(d.aggregateRating).toMatchObject({ ratingValue: 4.5, reviewCount: 2, bestRating: 5 });
    expect((d.review as unknown[]).length).toBe(1);
  });
  it("marks out-of-stock products", () => {
    expect(productJsonLd({ ...mat, in_stock: false }).offers.availability).toBe("https://schema.org/OutOfStock");
  });
  it("cannot break out of the script tag", () => {
    const out = jsonLdScript({ name: "</script><script>alert(1)</script>" });
    expect(out).not.toContain("</script>");
    expect(JSON.parse(out).name).toBe("</script><script>alert(1)</script>");
  });
});
