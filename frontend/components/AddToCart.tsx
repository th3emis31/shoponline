"use client";

import Link from "next/link";
import { useState } from "react";
import { addToCart } from "@/lib/client";

export default function AddToCart({ productId, inStock }: { productId: string; inStock: boolean }) {
  const [state, setState] = useState<"idle" | "busy" | "added">("idle");
  const [error, setError] = useState("");

  if (!inStock) return <button className="btn" disabled>Out of stock</button>;

  async function onClick() {
    setState("busy");
    setError("");
    try {
      await addToCart(productId, 1);
      setState("added");
    } catch (err) {
      setError((err as Error).message);
      setState("idle");
    }
  }

  return (
    <div>
      <button className="btn" onClick={onClick} disabled={state === "busy"}>
        {state === "busy" ? "Adding…" : "Add to cart"}
      </button>
      {state === "added" && (
        <p role="status">Added. <Link href="/cart">View cart</Link></p>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}
