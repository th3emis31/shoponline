import type { MetadataRoute } from "next";
import { getProducts } from "@/lib/api";
import { site } from "@/lib/site";

export const dynamic = "force-dynamic";

const STATIC_PAGES = ["", "/shop", "/about", "/contact", "/faq", "/shipping", "/returns", "/privacy", "/terms", "/cookies"];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const pages: MetadataRoute.Sitemap = STATIC_PAGES.map((path) => ({ url: `${site.url}${path}` }));
  try {
    const products = await getProducts();
    for (const p of products) pages.push({ url: `${site.url}/products/${p.id}` });
  } catch {
    // Backend unavailable: still serve the static pages rather than an error.
  }
  return pages;
}
