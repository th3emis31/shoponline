import type { MetadataRoute } from "next";
import { getProducts } from "@/lib/api";
import { ROOMS } from "@/lib/catalog";
import { guides } from "@/lib/guides";
import { site } from "@/lib/site";

export const dynamic = "force-dynamic";

const STATIC_PAGES = ["", "/shop", "/about", "/contact", "/faq", "/shipping", "/returns", "/privacy", "/terms", "/cookies", "/guides"];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const pages: MetadataRoute.Sitemap = STATIC_PAGES.map((path) => ({ url: `${site.url}${path}` }));
  for (const g of guides) pages.push({ url: `${site.url}/guides/${g.slug}` });
  for (const room of Object.keys(ROOMS)) pages.push({ url: `${site.url}/shop?room=${room}` });
  try {
    const products = await getProducts();
    for (const p of products) pages.push({ url: `${site.url}/products/${p.id}` });
  } catch {
    // Backend unavailable: still serve the static pages rather than an error.
  }
  return pages;
}
