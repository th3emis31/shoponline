"use client";

import { useRouter } from "next/navigation";
import { rememberOrderEmail } from "@/lib/client";

export default function TrackPage() {
  const router = useRouter();
  return (
    <>
      <h1>Track your order</h1>
      <p className="muted">Enter the order number from your confirmation and the email you used.</p>
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const id = String(f.get("order") ?? "").trim();
          rememberOrderEmail(String(f.get("email") ?? "").trim());
          router.push(`/order/${encodeURIComponent(id)}`);
        }}
      >
        <label>Order number<input name="order" required /></label>
        <label>Email<input name="email" type="email" required /></label>
        <button className="btn" type="submit">Track order</button>
      </form>
    </>
  );
}
