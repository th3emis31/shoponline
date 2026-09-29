"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CART_EVENT, peekCart } from "@/lib/client";
import type { Cart } from "@/lib/types";

const count = (c: Cart | null) => (c ? c.items.reduce((n, i) => n + i.quantity, 0) : 0);

export default function CartBadge() {
  const [n, setN] = useState(0);
  useEffect(() => {
    peekCart().then((c) => setN(count(c)));
    const onChange = (e: Event) => setN(count((e as CustomEvent<Cart | null>).detail));
    window.addEventListener(CART_EVENT, onChange);
    return () => window.removeEventListener(CART_EVENT, onChange);
  }, []);
  return (
    <Link href="/cart" className="cart-link">
      Cart{n > 0 && <span className="cart-count" data-testid="cart-count" aria-label={`${n} item${n === 1 ? "" : "s"}`}>{n}</span>}
    </Link>
  );
}
