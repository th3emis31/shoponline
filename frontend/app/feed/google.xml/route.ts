import { existsSync } from "node:fs";
import path from "node:path";
import { getProducts } from "@/lib/api";
import { entry } from "@/lib/catalog";
import { googleFeed } from "@/lib/feed";
import { site } from "@/lib/site";

export const dynamic = "force-dynamic";

/** Real product photos: put them in frontend/public/products/<product-id>.jpg (or .png / .webp). */
function photo(id: string): string | null {
  for (const ext of ["jpg", "jpeg", "png", "webp"]) {
    if (existsSync(path.join(process.cwd(), "public", "products", `${id}.${ext}`))) return `/products/${id}.${ext}`;
  }
  return null;
}

export async function GET() {
  const products = await getProducts().catch(() => []);
  const body = googleFeed(products, entry, photo, site);
  return new Response(body, { headers: { "Content-Type": "application/xml; charset=utf-8", "Cache-Control": "public, max-age=3600" } });
}
