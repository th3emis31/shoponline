"use client";

import { useState } from "react";
import { api } from "@/lib/client";

/** Contact form: lands in Admin > Support; a person replies within 1 business day. */
export default function ContactForm() {
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const r = await api<{ message: string }>("/api/contact", {
        method: "POST",
        body: JSON.stringify({
          name: f.get("name"), email: f.get("email"), topic: f.get("topic"), message: f.get("message"),
          order_id: String(f.get("order_id") ?? "").trim() || null, website: f.get("website") ?? "",
        }),
      });
      setDone(r.message);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }
  if (done) return <p className="notice" role="status" data-testid="contact-done">{done}</p>;
  return (
    <form className="stack" onSubmit={onSubmit} data-testid="contact-form">
      <label>Your name<input name="name" autoComplete="name" required maxLength={200} /></label>
      <label>Your email<input name="email" type="email" autoComplete="email" required /></label>
      <label>Topic
        <select name="topic" required defaultValue="">
          <option value="" disabled>Choose…</option>
          <option value="order">My order</option>
          <option value="return">Returns and refunds</option>
          <option value="product">A product question</option>
          <option value="other">Something else</option>
        </select>
      </label>
      <label>Order number (if about an order)<input name="order_id" maxLength={36} /></label>
      <label>Message<textarea name="message" rows={5} required minLength={5} maxLength={5000} /></label>
      {/* Honeypot for bots; hidden from people and screen readers. */}
      <div aria-hidden="true" style={{ position: "absolute", left: "-10000px", width: 1, height: 1, overflow: "hidden" }}>
        <label>Website<input name="website" tabIndex={-1} autoComplete="off" /></label>
      </div>
      <p className="muted small">We use your details only to answer you. See our <a href="/privacy">privacy notice</a>.</p>
      <button className="btn" type="submit" disabled={busy}>{busy ? "Sending…" : "Send message"}</button>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  );
}
