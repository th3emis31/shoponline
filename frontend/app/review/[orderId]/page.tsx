"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/client";

type Form = { order_id: string; display_name: string; items: { product_id: string; name: string; reviewed: boolean }[] };

function Stars({ name }: { name: string }) {
  return (
    <fieldset className="stars">
      <legend>Your rating</legend>
      {[5, 4, 3, 2, 1].map((n) => (
        <label key={n}>
          <input type="radio" name={name} value={n} required /> {n} star{n > 1 ? "s" : ""}
        </label>
      ))}
    </fieldset>
  );
}

function ReviewItem({ orderId, token, item }: { orderId: string; token: string; item: Form["items"][0] }) {
  const [done, setDone] = useState(item.reviewed ? "You've already reviewed this. Thank you!" : "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const r = await api<{ message: string }>(`/api/reviews/${encodeURIComponent(orderId)}`, {
        method: "POST",
        body: JSON.stringify({
          token, product_id: item.product_id, rating: Number(f.get("rating")),
          title: String(f.get("title") ?? ""), body: String(f.get("body") ?? ""),
        }),
      });
      setDone(r.message);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }
  return (
    <section className="panel" data-testid={`review-${item.product_id}`}>
      <h2>{item.name}</h2>
      {done ? <p className="notice" role="status">{done}</p> : (
        <form className="stack" onSubmit={onSubmit}>
          <Stars name="rating" />
          <label>Headline (optional)<input name="title" maxLength={120} /></label>
          <label>Your review (optional)<textarea name="body" rows={4} maxLength={2000} /></label>
          <p className="muted small">Please don&apos;t include phone numbers, addresses or other personal details.</p>
          <button className="btn" type="submit" disabled={busy}>{busy ? "Sending…" : "Send review"}</button>
          {error && <p className="error" role="alert">{error}</p>}
        </form>
      )}
    </section>
  );
}

function Review() {
  const { orderId } = useParams<{ orderId: string }>();
  const token = useSearchParams().get("token") ?? "";
  const [form, setForm] = useState<Form | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Form>(`/api/reviews/${encodeURIComponent(orderId)}?token=${encodeURIComponent(token)}`)
      .then(setForm).catch((e: Error) => setError(e.message));
  }, [orderId, token]);
  if (error) return <div className="prose"><h1>Write a review</h1><p className="error" data-testid="review-error">{error}</p></div>;
  if (!form) return <p>Loading…</p>;
  return (
    <div className="prose">
      <h1>Write a review</h1>
      <p>
        Good or bad, an honest review helps other people choose. We publish every genuine review, including
        critical ones. It will show as <strong>{form.display_name}</strong>, marked &ldquo;Verified buyer&rdquo;.
      </p>
      {form.items.map((i) => <ReviewItem key={i.product_id} orderId={form.order_id} token={token} item={i} />)}
      <p><Link href="/shop">Back to the shop</Link></p>
    </div>
  );
}

export default function ReviewPage() {
  return <Suspense fallback={<p>Loading…</p>}><Review /></Suspense>;
}
