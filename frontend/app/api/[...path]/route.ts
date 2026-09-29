/**
 * Same-origin proxy: browser -> /api/* -> FastAPI backend.
 * API_URL is read per request (not at build time), so one build works in any
 * environment. The backend URL is never exposed to the browser, and admin
 * endpoints are not reachable through the public site.
 */
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const FORWARD_REQUEST_HEADERS = ["content-type", "stripe-signature", "accept"];

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (path[0] === "admin") {
    return Response.json({ error: "Not found" }, { status: 404 });
  }
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  const target = `${apiUrl}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }
  const hasBody = !["GET", "HEAD"].includes(req.method);

  try {
    const res = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: "no-store",
      redirect: "manual",
    });
    return new Response(res.body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json({ error: "Shop is temporarily unavailable. Please try again." }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST, proxy as DELETE, proxy as PUT, proxy as PATCH };
