"use client";

import { useCallback, useEffect, useState } from "react";

type Call = <T>(path: string, init?: RequestInit) => Promise<T>;
type Reply = { id: number; body: string; by: string | null; created_at: string };
type Ticket = {
  id: number; name: string; email: string; order_id: string | null; topic: string; message: string;
  status: "open" | "replied" | "closed"; due_at: string; overdue: boolean; created_at: string; replies: Reply[];
};
type Inbox = { open: number; overdue: number; on_time_rate: number | null; topics: Record<string, string>; templates: Record<string, string>; tickets: Ticket[] };

const when = (s: string) => new Date(s).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

function TicketCard({ t, inbox, call, onError, reload }: { t: Ticket; inbox: Inbox; call: Call; onError: (m: string) => void; reload: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  async function applyTemplate(key: string) {
    if (!key) return;
    try { setText((await call<{ text: string }>(`support/${t.id}/template/${key}`)).text); } catch (e) { onError((e as Error).message); }
  }
  async function aiDraft() {
    setBusy(true);
    try {
      const r = await call<{ output: string; draft_mark: string }>("ai/run", { method: "POST", body: JSON.stringify({ agent: "customer", subject: String(t.id) }) });
      const draft = r.output.split(r.draft_mark)[1]?.trim();
      if (draft) setText(draft);
    } catch (e) { onError((e as Error).message); } finally { setBusy(false); }
  }
  async function send(close: boolean) {
    setBusy(true);
    try {
      await call(`support/${t.id}/reply`, { method: "POST", body: JSON.stringify({ body: text, close }) });
      setText("");
      reload();
    } catch (e) { onError((e as Error).message); } finally { setBusy(false); }
  }
  async function setStatus(status: "open" | "closed") {
    try { await call(`support/${t.id}/status`, { method: "POST", body: JSON.stringify({ status }) }); reload(); } catch (e) { onError((e as Error).message); }
  }
  return (
    <section className="panel" data-testid={`ticket-${t.id}`} style={{ marginBottom: 16 }}>
      <p>
        <strong>#{t.id} · {inbox.topics[t.topic] ?? t.topic}</strong> · {t.name} &lt;{t.email}&gt;
        {t.order_id && <> · order <code>{t.order_id.slice(0, 8)}</code></>}
        <br />
        <span className="small muted">Received {when(t.created_at)} · reply by {when(t.due_at)}</span>{" "}
        {t.overdue ? <strong className="error">Overdue</strong> : <span className="small">{t.status}</span>}
      </p>
      <p style={{ whiteSpace: "pre-wrap" }}>{t.message}</p>
      {t.replies.map((r) => (
        <div key={r.id} className="small" style={{ borderLeft: "3px solid var(--line)", paddingLeft: 10, margin: "8px 0", whiteSpace: "pre-wrap" }}>
          <span className="muted">{r.by ?? "admin"} · {when(r.created_at)}</span>{"\n"}{r.body}
        </div>
      ))}
      {t.status !== "closed" ? (
        <div className="stack">
          <label>Start from a template
            <select defaultValue="" onChange={(e) => applyTemplate(e.target.value)} aria-label={`Template for message ${t.id}`}>
              <option value="">Choose…</option>
              {Object.entries(inbox.templates).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <p><button className="btn link" onClick={aiDraft} disabled={busy}>Draft with the AI assistant</button></p>
          <label>Reply to {t.name}<textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} /></label>
          <p className="small muted">Read it through and fill in anything in [brackets] before sending.</p>
          <p>
            <button className="btn" disabled={busy || !text.trim() || text.includes("[")} onClick={() => send(false)}>Send reply</button>{" "}
            <button className="btn secondary" disabled={busy || !text.trim() || text.includes("[")} onClick={() => send(true)}>Send and close</button>{" "}
            <button className="btn link" onClick={() => setStatus("closed")}>Close without reply</button>
          </p>
        </div>
      ) : <p><button className="btn link" onClick={() => setStatus("open")}>Reopen</button></p>}
    </section>
  );
}

/** Customer messages from the contact form. Target: a reply within 1 business day. */
export default function SupportTab({ call, onError }: { call: Call; onError: (m: string) => void }) {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [show, setShow] = useState<"open" | "all">("open");
  const load = useCallback(() => call<Inbox>("support").then(setInbox).catch((e: Error) => onError(e.message)), [call, onError]);
  useEffect(() => { load(); }, [load]);
  if (!inbox) return <p>Loading…</p>;
  const list = show === "open" ? inbox.tickets.filter((t) => t.status === "open") : inbox.tickets;
  return (
    <div data-testid="support">
      <p className="notice">
        <strong>{inbox.open}</strong> waiting · <strong className={inbox.overdue ? "error" : ""}>{inbox.overdue}</strong> past the
        1-business-day target · answered on time: <strong>{inbox.on_time_rate == null ? "—" : `${Math.round(inbox.on_time_rate * 100)}%`}</strong>
      </p>
      <p>
        <label>Show{" "}
          <select value={show} onChange={(e) => setShow(e.target.value as "open" | "all")} aria-label="Show messages">
            <option value="open">Waiting for a reply</option><option value="all">All messages</option>
          </select>
        </label>
      </p>
      {list.length === 0 ? <p className="muted">Nothing waiting. 🎉</p> : list.map((t) => (
        <TicketCard key={t.id} t={t} inbox={inbox} call={call} onError={onError} reload={load} />
      ))}
    </div>
  );
}
