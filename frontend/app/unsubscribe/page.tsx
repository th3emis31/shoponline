"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/client";

function Unsubscribe() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (!token) { setState("error"); setMessage("This unsubscribe link is incomplete."); return; }
    api<{ message: string }>("/api/email/unsubscribe", { method: "POST", body: JSON.stringify({ token }) })
      .then((r) => { setMessage(r.message); setState("done"); })
      .catch((e: Error) => { setMessage(e.message); setState("error"); });
  }, [token]);
  return (
    <div className="prose">
      <h1>Email preferences</h1>
      {state === "working" && <p>Unsubscribing…</p>}
      {state !== "working" && <p className={state === "error" ? "error" : "notice"} role="status" data-testid="unsubscribe-result">{message}</p>}
      <p>You&apos;ll still get emails about orders you place, such as confirmations and delivery updates.</p>
      <p><Link href="/">Back to the shop</Link></p>
    </div>
  );
}

export default function UnsubscribePage() {
  return <Suspense fallback={<p>Loading…</p>}><Unsubscribe /></Suspense>;
}
