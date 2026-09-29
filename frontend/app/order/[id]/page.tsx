"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { getOrder, recalledOrderEmail, rememberOrderEmail } from "@/lib/client";
import { formatGBP } from "@/lib/money";
import type { Order } from "@/lib/types";

const STATUS_TEXT: Record<Order["status"], string> = {
  placed: "Order placed",
  pending_payment: "Waiting for payment confirmation",
  paid: "Paid — we're preparing your order",
  cancelled: "Cancelled — no payment was taken",
  payment_review: "Payment under review — we'll email you",
};

export default function OrderPage() {
  const { id } = useParams<{ id: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [needsEmail, setNeedsEmail] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (email: string) => {
    setError("");
    try {
      setOrder(await getOrder(id, email));
      setNeedsEmail(false);
    } catch {
      setError("We couldn't find an order with that number and email.");
      setNeedsEmail(true);
    }
  }, [id]);

  useEffect(() => {
    const email = recalledOrderEmail();
    if (email) load(email);
    else setNeedsEmail(true);
  }, [load]);

  if (needsEmail) {
    return (
      <>
        <h1>Find your order</h1>
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            const email = String(new FormData(e.currentTarget).get("email") ?? "");
            rememberOrderEmail(email);
            load(email);
          }}
        >
          <label>Email used for the order<input name="email" type="email" required /></label>
          <button className="btn" type="submit">Show order</button>
          {error && <p className="error" role="alert">{error}</p>}
        </form>
      </>
    );
  }

  if (!order) return <p>Loading your order…</p>;

  return (
    <>
      <h1>Thank you</h1>
      <p className="notice" data-testid="order-status">{STATUS_TEXT[order.status] ?? order.status}</p>
      <p>Order number: <strong>{order.id}</strong></p>
      <table className="lines">
        <tbody>
          {order.items.map((l) => (
            <tr key={l.product_id}>
              <td>{l.name} × {l.quantity}</td>
              <td className="num">{formatGBP(l.line_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="totals">
        <div><span>Subtotal</span><span>{formatGBP(order.subtotal)}</span></div>
        <div><span>UK delivery</span><span>{order.shipping === 0 ? "Free" : formatGBP(order.shipping)}</span></div>
        <div className="grand"><span>Total</span><span>{formatGBP(order.total)}</span></div>
      </div>
      <p><Link href="/shop">Continue shopping</Link></p>
    </>
  );
}
