"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/client";

/** Footer sign-up for tips and offers: explicit, unticked opt-in. */
export default function NewsletterForm() {
  const [text, setText] = useState("Email me tips for small spaces and occasional offers from NOVAHAUS. I can unsubscribe at any time.");
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    fetch("/api/marketing/consent").then((r) => r.json()).then((d) => { if (d?.text) setText(d.text); }).catch(() => {});
  }, []);
  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setError("");
    try {
      const r = await api<{ message: string }>("/api/newsletter", {
        method: "POST", body: JSON.stringify({ email: f.get("email"), consent: f.get("consent") === "on" }),
      });
      setDone(r.message);
    } catch (err) { setError((err as Error).message); }
  }
  if (done) return <p role="status" data-testid="newsletter-done">{done}</p>;
  return (
    <form className="waitlist" onSubmit={onSubmit} data-testid="newsletter">
      <strong>Tips for small spaces</strong>
      <div className="waitlist-row">
        <label className="sr-only" htmlFor="nl-email">Email for tips</label>
        <input id="nl-email" name="email" type="email" required placeholder="you@example.com" autoComplete="email" />
        <button className="btn secondary" type="submit">Sign up</button>
      </div>
      <label className="consent"><input type="checkbox" name="consent" required /> <span>{text}</span></label>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  );
}
