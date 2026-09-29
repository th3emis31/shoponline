import type { MetadataRoute } from "next";
import { site } from "@/lib/site";

export const dynamic = "force-dynamic";

export default function robots(): MetadataRoute.Robots {
  // Preview site: ask search engines not to index anything until launch.
  if (!site.launchReady) {
    return { rules: [{ userAgent: "*", disallow: "/" }] };
  }
  return {
    rules: [{
      userAgent: "*",
      allow: "/",
      disallow: ["/admin", "/admin-api/", "/api/", "/cart", "/order/", "/track"],
    }],
    sitemap: `${site.url}/sitemap.xml`,
  };
}
