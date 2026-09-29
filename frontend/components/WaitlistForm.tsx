"use client";

import { useEffect, useState } from "react";
import { joinWaitlist } from "@/lib/client";

/** "Notify me at launch": explicit, unticked opt-in (UK PECR / UK GDPR). */
export default function WaitlistForm({ productId = null, heading }: { productId?: string | null; heading?: string }) {
  const [consentText, setConsentText] = useState(
    "Email me once when NOVAHAUS launches (or when this product is available). No other marketing. I can unsubscribe at any time.",
  );
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const inputId = `wl-${productId ?? "shop"}`;

  useEffect(() => {
    fetch("/api/waitlist/consent")
      .then((r) => r.json())
      .then((d) => { if (d?.text) setConsentText(d.text); })
      .catch(() => {});
  }, []);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setState("busy");
    setError("");
    try {
      const r = await joinWaitlist(String(f.get("email") ?? ""), productId, f.get("consent") === "on");
      setMessage(r.message);
      setState("done");
    } catch (err) {
      setError((err as Error).message);
      setState("idle");
    }
  }

  if (state === "done") return <p className="notice" role="status" data-testid="waitlist-done">{message}</p>;
  return (
    <form className="waitlist" onSubmit={onSubmit} data-testid="waitlist">
      {heading && <strong>{heading}</strong>}
      <div className="waitlist-row">
        <label className="sr-only" htmlFor={inputId}>Email for launch news</label>
        <input id={inputId} name="email" type="email" required placeholder="you@example.com" autoComplete="email" />
        <button className="btn" type="submit" disabled={state === "busy"}>{state === "busy" ? "Joining…" : "Notify me"}</button>
      </div>
      <label className="consent">
        <input type="checkbox" name="consent" required /> <span>{consentText}</span>
      </label>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  );
}
