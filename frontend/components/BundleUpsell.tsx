"use client";

import { useEffect, useState } from "react";
import { BUNDLE_ID, BUNDLE_PARTS } from "@/lib/catalog";
import { addToCart, api, removeFromCart } from "@/lib/client";
import { formatGBP } from "@/lib/money";
import type { Cart, Product } from "@/lib/types";

const isPart = (id: string) => (BUNDLE_PARTS as readonly string[]).includes(id);

/**
 * If the cart holds some Desk Reset pieces (one of each at most), offer the set
 * with the honest price difference. Switching swaps the pieces for the set.
 */
export default function BundleUpsell({ cart, onChange }: { cart: Cart; onChange: (c: Cart) => void }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api<Product[]>("/api/products").then(setProducts).catch(() => {}); }, []);

  const bundle = products.find((p) => p.id === BUNDLE_ID);
  const parts = products.filter((p) => isPart(p.id));
  const inCart = cart.items.filter((i) => isPart(i.product_id));
  if (!bundle || !bundle.in_stock || parts.length !== BUNDLE_PARTS.length) return null;
  if (cart.items.some((i) => i.product_id === BUNDLE_ID)) return null;
  if (inCart.length === 0 || inCart.some((i) => i.quantity !== 1)) return null;

  const separately = parts.reduce((n, p) => n + p.price, 0);
  const saving = separately - bundle.price;
  if (saving <= 0) return null;
  const extra = bundle.price - inCart.reduce((n, i) => n + i.line_total, 0);
  const missing = parts.filter((p) => !inCart.some((i) => i.product_id === p.id)).map((p) => p.name);

  async function switchToSet() {
    setBusy(true);
    setError("");
    try {
      // Add the set first: if that fails (e.g. no stock) the cart is left as it was.
      let updated = await addToCart(BUNDLE_ID, 1);
      for (const i of inCart) updated = await removeFromCart(updated.id, i.product_id);
      onChange(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="upsell" data-testid="bundle-upsell">
      <strong>Complete the Desk Reset set and save {formatGBP(saving)}</strong>
      <p className="muted">
        {missing.length > 0
          ? `Add ${missing.join(" and ")} for ${extra > 0 ? `just ${formatGBP(extra)} more` : "no extra cost"}. `
          : "You already have all three pieces. "}
        The set is {formatGBP(bundle.price)} instead of {formatGBP(separately)}, in one parcel.
      </p>
      <button className="btn" onClick={switchToSet} disabled={busy}>
        {busy ? "Switching…" : `Switch to the set${extra > 0 ? ` (+${formatGBP(extra)})` : ""}`}
      </button>
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}
