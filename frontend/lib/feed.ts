import type { Product } from "./types";
import type { CatalogEntry } from "./catalog";

export type FeedSite = { url: string; name: string; shippingFee: number; freeShippingThreshold: number };

export const xml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");

const gbp = (p: number) => `${(p / 100).toFixed(2)} GBP`;

/**
 * Google Merchant Center product feed (RSS 2.0 + g: namespace). Products without a
 * real photo are left out: Google rejects items without an image, and illustrations
 * must never be presented as photos.
 */
export function googleFeed(products: Product[], copy: (id: string) => CatalogEntry | undefined,
                           photo: (id: string) => string | null, site: FeedSite): string {
  const items: string[] = [];
  const skipped: string[] = [];
  for (const p of products) {
    const img = photo(p.id);
    if (!img) { skipped.push(p.id); continue; }
    const c = copy(p.id);
    const desc = c ? `${c.tagline} ${c.benefits.join(". ")}.` : p.name;
    const shipping = p.price >= site.freeShippingThreshold ? 0 : site.shippingFee;
    items.push([
      "    <item>",
      `      <g:id>${xml(p.id)}</g:id>`,
      `      <g:title>${xml(p.name)}</g:title>`,
      `      <g:description>${xml(desc)}</g:description>`,
      `      <g:link>${xml(`${site.url}/products/${p.id}`)}</g:link>`,
      `      <g:image_link>${xml(img.startsWith("http") ? img : `${site.url}${img}`)}</g:image_link>`,
      `      <g:availability>${p.in_stock ? "in_stock" : "out_of_stock"}</g:availability>`,
      `      <g:price>${gbp(p.price)}</g:price>`,
      `      <g:brand>${xml(site.name)}</g:brand>`,
      "      <g:condition>new</g:condition>",
      "      <g:identifier_exists>no</g:identifier_exists>",
      ...(p.is_bundle ? ["      <g:is_bundle>yes</g:is_bundle>"] : []),
      `      <g:shipping><g:country>GB</g:country><g:price>${gbp(shipping)}</g:price></g:shipping>`,
      "    </item>",
    ].join("\n"));
  }
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">',
    "  <channel>",
    `    <title>${xml(site.name)}</title>`,
    `    <link>${xml(site.url)}</link>`,
    `    <description>${xml(`${site.name} products`)}</description>`,
    ...(skipped.length ? [`    <!-- Left out until a real photo is added to public/products/: ${xml(skipped.join(", "))} -->`] : []),
    ...items,
    "  </channel>",
    "</rss>",
    "",
  ].join("\n");
}
