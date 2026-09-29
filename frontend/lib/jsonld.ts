import type { Product } from "./types";
import { site } from "./site";

/**
 * schema.org Product data for search engines. Deliberately contains no
 * ratings or reviews: the blueprint forbids showing any we haven't earned.
 */
export function productJsonLd(p: Product) {
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
  };
}

/** Serialise for a <script> tag; escapes "<" so content can never close the tag. */
export function jsonLdScript(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
