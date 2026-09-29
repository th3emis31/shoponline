/**
 * Admin proxy: /admin-api/* -> backend /api/admin/*.
 * The backend checks X-Admin-Token on every call; this route only forwards it.
 */
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  const target = `${apiUrl}/api/admin/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers({ "content-type": "application/json" });
  const token = req.headers.get("x-admin-token");
  if (token) headers.set("x-admin-token", token);
  try {
    const res = await fetch(target, {
      method: req.method,
      headers,
      body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.text(),
      cache: "no-store",
    });
    return new Response(res.body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json", "cache-control": "no-store" },
    });
  } catch {
    return Response.json({ error: "Backend unavailable" }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST, proxy as PATCH };
