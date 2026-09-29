import type { Product, ReviewSummary } from "./types";
import { site } from "./site";

/**
 * schema.org Product data for search engines. Ratings appear only once real,
 * published verified-buyer reviews exist: the blueprint forbids any we haven't earned.
 */
export function productJsonLd(p: Product, reviews?: ReviewSummary | null) {
  const rated = reviews && reviews.count > 0 && reviews.average != null;
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: p.name,
    sku: p.id,
    brand: { "@type": "Brand", name: site.name },
    url: `${site.url}/products/${p.id}`,
    offers: {
      "@type": "Offer",
      price: (p.price / 100).toFixed(2),
      priceCurrency: "GBP",
      availability: p.in_stock ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
      url: `${site.url}/products/${p.id}`,
    },
    ...(rated
      ? {
          aggregateRating: {
            "@type": "AggregateRating", ratingValue: reviews.average, reviewCount: reviews.count, bestRating: 5, worstRating: 1,
          },
          review: reviews.reviews.slice(0, 5).map((r) => ({
            "@type": "Review",
            author: { "@type": "Person", name: r.name },
            reviewRating: { "@type": "Rating", ratingValue: r.rating, bestRating: 5, worstRating: 1 },
            ...(r.title ? { name: r.title } : {}),
            ...(r.body ? { reviewBody: r.body } : {}),
          })),
        }
      : {}),
  };
}

/** Serialise for a <script> tag; escapes "<" so content can never close the tag. */
export function jsonLdScript(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
