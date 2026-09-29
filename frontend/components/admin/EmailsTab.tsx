"use client";

import { Fragment, useCallback, useEffect, useState } from "react";

type Call = <T>(path: string, init?: RequestInit) => Promise<T>;
type Msg = {
  id: number; to: string; subject: string; body: string; kind: string; flow: string; step: number;
  status: string; error: string; send_after: string; sent_at: string | null;
};
type Outbox = { mode: string; subscribers: { marketing: number; launch_only: number }; messages: Msg[] };

const when = (s: string | null) => (s ? new Date(s).toLocaleString("en-GB") : "—");

/** Owner-only: every email the shop sends (or would send), and the launch email button. */
export default function EmailsTab({ call, onError }: { call: Call; onError: (m: string) => void }) {
  const [data, setData] = useState<Outbox | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const load = useCallback(() => call<Outbox>("emails").then(setData).catch((e: Error) => onError(e.message)), [call, onError]);
  useEffect(() => { load(); }, [load]);

  async function launch() {
    if (!window.confirm("Send the one launch email to everyone who asked for it? Each person gets it at most once.")) return;
    try {
      const r = await call<{ queued: number }>("emails/launch", { method: "POST" });
      setNote(`Queued ${r.queued} launch email(s).`);
      await load();
    } catch (e) { onError((e as Error).message); }
  }

  if (!data) return <p>Loading…</p>;
  return (
    <div data-testid="emails">
      <p className="notice">
        {data.mode === "smtp"
          ? <>Emails are <strong>sent</strong> through your email service.</>
          : <>Test mode: emails are <strong>kept here and not sent</strong>. Add a free SMTP service in the backend settings to send them (see DEPLOY.md).</>}
        {" "}Subscribers: <strong>{data.subscribers.marketing}</strong> tips and offers,{" "}
        <strong>{data.subscribers.launch_only}</strong> launch email only.
      </p>
      <p>
        <button className="btn secondary" onClick={launch}>Send launch email to the waitlist</button>{" "}
        {note && <span role="status">{note}</span>}
      </p>
      {data.messages.length === 0 ? <p className="muted">No emails yet.</p> : (
        <div style={{ overflowX: "auto" }}>
          <table className="lines">
            <thead><tr><th>To</th><th>Subject</th><th>Type</th><th>Status</th><th>When</th></tr></thead>
            <tbody>
              {data.messages.map((m) => (
                <Fragment key={m.id}>
                  <tr onClick={() => setOpen(open === m.id ? null : m.id)} style={{ cursor: "pointer" }}>
                    <td>{m.to}</td>
                    <td>{m.subject}</td>
                    <td className="muted small">{m.flow} {m.step} · {m.kind}</td>
                    <td><strong>{m.status === "outbox" ? "kept (test mode)" : m.status}</strong>{m.error && <><br /><span className="muted small">{m.error}</span></>}</td>
                    <td className="small">{m.sent_at ? when(m.sent_at) : `after ${when(m.send_after)}`}</td>
                  </tr>
                  {open === m.id && (
                    <tr><td colSpan={5}><pre className="panel" style={{ whiteSpace: "pre-wrap", margin: 0 }}>{m.body}</pre></td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
