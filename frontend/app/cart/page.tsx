"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import BundleUpsell from "@/components/BundleUpsell";
import FreeDeliveryBar from "@/components/FreeDeliveryBar";
import { checkout, ensureCart, removeFromCart } from "@/lib/client";
import { formatGBP } from "@/lib/money";
import type { Cart } from "@/lib/types";

export default function CartPage() {
  const router = useRouter();
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    ensureCart().then(setCart).catch((err: Error) => setError(err.message));
  }, []);

  async function remove(productId: string) {
    if (!cart) return;
    try {
      setCart(await removeFromCart(cart.id, productId));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!cart) return;
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const order = await checkout(cart.id, {
        name: String(form.get("name") ?? ""),
        email: String(form.get("email") ?? ""),
        address: String(form.get("address") ?? ""),
      });
      if (order.checkout_url) {
        window.location.assign(order.checkout_url); // Stripe hosted payment page
      } else {
        router.push(`/order/${order.id}`);
      }
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  if (!cart) return <p>{error ? <span className="error">{error}</span> : "Loading your cart…"}</p>;

  if (cart.items.length === 0) {
    return (
      <>
        <h1>Your cart</h1>
        <p>Your cart is empty. <Link href="/shop">Browse the collection</Link>.</p>
      </>
    );
  }

  return (
    <>
      <h1>Your cart</h1>
      <table className="lines">
        <thead>
          <tr><th>Item</th><th className="num">Qty</th><th className="num">Price</th><th /></tr>
        </thead>
        <tbody>
          {cart.items.map((line) => (
            <tr key={line.product_id}>
              <td>{line.name}</td>
              <td className="num">{line.quantity}</td>
              <td className="num">{formatGBP(line.line_total)}</td>
              <td className="num">
                <button className="btn link" onClick={() => remove(line.product_id)} aria-label={`Remove ${line.name}`}>Remove</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <FreeDeliveryBar subtotal={cart.subtotal} />
      <BundleUpsell cart={cart} onChange={setCart} />

      {/* All costs shown before payment (Blueprint section H checkout rules). */}
      <div className="totals" data-testid="totals">
        <div><span>Subtotal</span><span>{formatGBP(cart.subtotal)}</span></div>
        <div><span>UK delivery</span><span>{cart.shipping === 0 ? "Free" : formatGBP(cart.shipping)}</span></div>
        <div className="grand"><span>Total (inc. VAT)</span><span>{formatGBP(cart.total)}</span></div>
      </div>

      <h2>Delivery details</h2>
      <form className="stack" onSubmit={onSubmit}>
        <label>Full name<input name="name" autoComplete="name" required maxLength={200} /></label>
        <label>Email (for your receipt and tracking)<input name="email" type="email" autoComplete="email" required /></label>
        <label>Delivery address<textarea name="address" autoComplete="street-address" required rows={3} maxLength={500} /></label>
        <p className="muted">
          By placing the order you accept our <Link href="/terms">terms</Link>. You can cancel within 14 days of
          delivery — see <Link href="/returns">returns</Link>.
        </p>
        <button className="btn" type="submit" disabled={busy}>
          {busy ? "Placing order…" : `Continue to payment · ${formatGBP(cart.total)}`}
        </button>
        {error && <p className="error" role="alert">{error}</p>}
      </form>
    </>
  );
}
