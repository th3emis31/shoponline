"use client";

import type { Cart, Order } from "./types";

const CART_KEY = "novahaus.cartId";
const EMAIL_KEY = "novahaus.orderEmail";
export const CART_EVENT = "novahaus:cart";

/** Tell other components (e.g. the header cart count) that the cart changed. */
function announce(cart: Cart | null) {
  try {
    window.dispatchEvent(new CustomEvent(CART_EVENT, { detail: cart }));
  } catch {
    /* not in a browser (unit tests) */
  }
}

/** Browser-side API call through the same-origin /api proxy. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data?.detail) ? "Please check the highlighted details." : data?.detail;
    throw new Error(data?.error ?? detail ?? "Something went wrong. Please try again.");
  }
  return data as T;
}

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Returns the current cart, creating a new one if missing or expired. */
export async function ensureCart(): Promise<Cart> {
  const id = storage()?.getItem(CART_KEY);
  if (id) {
    try {
      return await api<Cart>(`/api/carts/${encodeURIComponent(id)}`);
    } catch {
      /* cart gone (e.g. after checkout) — create a fresh one */
    }
  }
  const cart = await api<Cart>("/api/carts", { method: "POST" });
  storage()?.setItem(CART_KEY, cart.id);
  return cart;
}

export async function addToCart(productId: string, quantity = 1): Promise<Cart> {
  const cart = await ensureCart();
  const updated = await api<Cart>(`/api/carts/${cart.id}/items`, {
    method: "POST",
    body: JSON.stringify({ product_id: productId, quantity }),
  });
  track("add_to_cart", productId);
  announce(updated);
  return updated;
}

export async function removeFromCart(cartId: string, productId: string): Promise<Cart> {
  const cart = await api<Cart>(`/api/carts/${cartId}/items/${encodeURIComponent(productId)}`, { method: "DELETE" });
  announce(cart);
  return cart;
}

/** Current cart without creating one (null if the visitor has none yet). */
export async function peekCart(): Promise<Cart | null> {
  const id = storage()?.getItem(CART_KEY);
  if (!id) return null;
  try {
    return await api<Cart>(`/api/carts/${encodeURIComponent(id)}`);
  } catch {
    return null;
  }
}

export async function joinWaitlist(email: string, productId: string | null, consent: boolean) {
  return api<{ ok: boolean; message: string }>("/api/waitlist", {
    method: "POST",
    body: JSON.stringify({ email, product_id: productId, consent }),
  });
}

export async function checkout(
  cartId: string,
  details: { name: string; email: string; address: string },
): Promise<Order> {
  track("begin_checkout");
  const order = await api<Order>(`/api/carts/${cartId}/checkout`, {
    method: "POST",
    body: JSON.stringify(details),
  });
  storage()?.removeItem(CART_KEY);
  rememberOrderEmail(details.email);
  announce(null);
  return order;
}

export function rememberOrderEmail(email: string) {
  try {
    window.sessionStorage.setItem(EMAIL_KEY, email);
  } catch {
    /* storage blocked — order page will ask for the email instead */
  }
}

export function recalledOrderEmail(): string {
  try {
    return window.sessionStorage.getItem(EMAIL_KEY) ?? "";
  } catch {
    return "";
  }
}

export async function getOrder(orderId: string, email: string): Promise<Order> {
  const qs = new URLSearchParams({ email });
  return api<Order>(`/api/orders/${encodeURIComponent(orderId)}?${qs}`);
}

/**
 * Anonymous funnel event. Fire-and-forget: never blocks or breaks the UI,
 * stores nothing in the browser, and sends no personal data.
 */
export function track(type: "view_product" | "add_to_cart" | "begin_checkout", productId?: string) {
  try {
    void fetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, product_id: productId ?? null }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* analytics must never affect shopping */
  }
}
