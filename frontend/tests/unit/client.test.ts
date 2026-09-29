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

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.stubGlobal("window", { localStorage: memoryStorage(), sessionStorage: memoryStorage() });
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
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
