import { beforeEach, describe, expect, it, vi } from "vitest";
import { addToCart, checkout, ensureCart, recalledOrderEmail } from "@/lib/client";

function memoryStorage(): Storage {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, v),
    removeItem: (k) => void m.delete(k),
    clear: () => m.clear(),
    key: (i) => [...m.keys()][i] ?? null,
    get length() { return m.size; },
  };
}

const emptyCart = (id: string) => ({ id, items: [], subtotal: 0, shipping: 0, total: 0 });

function respond(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }));
}

type FetchFn = (url: string, init?: RequestInit) => Promise<Response>;
let fetchMock: ReturnType<typeof vi.fn<FetchFn>>;

beforeEach(() => {
  vi.stubGlobal("window", { localStorage: memoryStorage(), sessionStorage: memoryStorage() });
  fetchMock = vi.fn<FetchFn>();
  // Analytics calls are fire-and-forget; answer them separately so they
  // don't consume the responses queued for the call under test.
  const eventsMock = (url: string, init?: RequestInit) =>
    url === "/api/events" ? Promise.resolve(new Response(null, { status: 204 })) : fetchMock(url, init);
  vi.stubGlobal("fetch", vi.fn(eventsMock));
});

describe("cart client", () => {
  it("creates a cart and remembers it", async () => {
    fetchMock.mockReturnValueOnce(respond(201, emptyCart("c1")));
    expect((await ensureCart()).id).toBe("c1");
    fetchMock.mockReturnValueOnce(respond(200, emptyCart("c1")));
    await ensureCart();
    expect(fetchMock.mock.calls[1][0]).toBe("/api/carts/c1");
  });

  it("replaces an expired cart", async () => {
    window.localStorage.setItem("novahaus.cartId", "old");
    fetchMock
      .mockReturnValueOnce(respond(404, { error: "Cart not found" }))
      .mockReturnValueOnce(respond(201, emptyCart("new")));
    expect((await ensureCart()).id).toBe("new");
    expect(window.localStorage.getItem("novahaus.cartId")).toBe("new");
  });

  it("surfaces backend error messages", async () => {
    fetchMock
      .mockReturnValueOnce(respond(201, emptyCart("c1")))
      .mockReturnValueOnce(respond(409, { error: "Not enough stock" }));
    await expect(addToCart("monitor-riser", 99)).rejects.toThrow("Not enough stock");
  });

  it("checkout clears the cart and remembers the email", async () => {
    window.localStorage.setItem("novahaus.cartId", "c1");
    fetchMock.mockReturnValueOnce(respond(201, { id: "o1", status: "placed" }));
    await checkout("c1", { name: "J", email: "j@example.com", address: "x" });
    expect(window.localStorage.getItem("novahaus.cartId")).toBeNull();
    expect(recalledOrderEmail()).toBe("j@example.com");
  });

  it("keeps the cart when checkout fails", async () => {
    window.localStorage.setItem("novahaus.cartId", "c1");
    fetchMock.mockReturnValueOnce(respond(502, { error: "Payment provider unavailable, please try again" }));
    await expect(checkout("c1", { name: "J", email: "j@example.com", address: "x" })).rejects.toThrow(/Payment provider/);
    expect(window.localStorage.getItem("novahaus.cartId")).toBe("c1");
  });
});

describe("track", () => {
  it("never throws, even when the network fails", async () => {
    const { track } = await import("@/lib/client");
    const failing = vi.fn(() => Promise.reject(new Error("offline")));
    vi.stubGlobal("fetch", failing);
    expect(() => track("view_product", "desk-mat")).not.toThrow();
    await new Promise((r) => setTimeout(r, 0));
    const body = JSON.parse((failing.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(body).toEqual({ type: "view_product", product_id: "desk-mat" });
  });
});
