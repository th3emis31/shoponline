"use client";

import { useCallback, useEffect, useState } from "react";
import { formatGBP } from "@/lib/money";

type Call = <T>(path: string, init?: RequestInit) => Promise<T>;

type Rec = {
  id: number; kind: string; target: string; payload: Record<string, number>; reason: string;
  impact: number; status: string; auto: boolean; decision_note: string; decided_by: string | null;
  result: string; created_at: string;
};
type Job = { job: string; schedule: string; last_run: string | null; last_status: string | null; last_message: string | null };
type Status = {
  enabled: boolean; jobs: Job[];
  limits: { auto_reorder_max: number; auto_reorder_weekly_max: number; auto_price_max_pct: number; min_contribution_margin: number };
};
type PO = {
  id: number; product_id: string; quantity: number; unit_cost: number; total: number; status: string;
  created_at: string; next_statuses: string[];
};

const when = (s: string | null) => (s ? new Date(s).toLocaleString("en-GB") : "never");

function describe(r: Rec) {
  if (r.kind === "reorder") return `Reorder ${r.payload.quantity} × ${r.target} (${formatGBP(r.impact)})`;
  if (r.kind === "price_change") return `Price ${r.target}: ${formatGBP(r.payload.old_price)} → ${formatGBP(r.payload.new_price)}`;
  return `${r.kind} ${r.target}`;
}

export function ApprovalsTab({ call, onError }: { call: Call; onError: (m: string) => void }) {
  const [recs, setRecs] = useState<Rec[]>([]);
  const load = useCallback(() => call<Rec[]>("recommendations?limit=50").then(setRecs).catch((e: Error) => onError(e.message)), [call, onError]);
  useEffect(() => { load(); }, [load]);

  async function decide(id: number, approve: boolean) {
    const note = window.prompt(approve ? "Approve. Optional note:" : "Reject. Optional reason:", "");
    if (note === null) return;
    try {
      await call(`recommendations/${id}/${approve ? "approve" : "reject"}`, { method: "POST", body: JSON.stringify({ note }) });
      await load();
    } catch (e) { onError((e as Error).message); }
  }

  const pending = recs.filter((r) => r.status === "pending");
  const done = recs.filter((r) => r.status !== "pending");
  return (
    <div data-testid="approvals">
      <h2 style={{ marginTop: 0 }}>Waiting for you ({pending.length})</h2>
      {pending.length === 0 && <p className="muted">Nothing to approve. Actions within your limits run by themselves.</p>}
      {pending.map((r) => (
        <div key={r.id} className="panel" style={{ marginBottom: 12 }} data-testid={`rec-${r.id}`}>
          <strong>{describe(r)}</strong>
          <p>{r.reason}</p>
          <p className="muted">Why it needs you: {r.decision_note}</p>
          <button className="btn" onClick={() => decide(r.id, true)}>Approve</button>{" "}
          <button className="btn secondary" onClick={() => decide(r.id, false)}>Reject</button>
        </div>
      ))}
      <h2>Recent decisions</h2>
      {done.length === 0 ? <p className="muted">None yet.</p> : (
        <div style={{ overflowX: "auto" }}>
        <table className="lines">
          <thead><tr><th>When</th><th>Action</th><th>Status</th><th>Decided by</th><th>Result</th></tr></thead>
          <tbody>
            {done.map((r) => (
              <tr key={r.id}>
                <td>{when(r.created_at)}</td>
                <td>{describe(r)}</td>
                <td>{r.status}{r.auto ? " (automatic)" : ""}</td>
                <td>{r.decided_by ?? "—"}</td>
                <td style={{ overflowWrap: "anywhere" }}>{r.result || r.decision_note}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
    </div>
  );
}

export function AutomationTab({ call, onError }: { call: Call; onError: (m: string) => void }) {
  const [st, setSt] = useState<Status | null>(null);
  const [report, setReport] = useState<{ day: string | null; content: string | null } | null>(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    try {
      setSt(await call<Status>("automation"));
      setReport(await call("reports/latest"));
    } catch (e) { onError((e as Error).message); }
  }, [call, onError]);
  useEffect(() => { load(); }, [load]);

  async function runNow(job: string) {
    setBusy(job);
    try { await call(`automation/run/${job}`, { method: "POST" }); await load(); }
    catch (e) { onError((e as Error).message); }
    finally { setBusy(""); }
  }

  if (!st) return <p>Loading…</p>;
  const l = st.limits;
  return (
    <div data-testid="automation">
      <p className="notice">
        Schedule is <strong>{st.enabled ? "ON" : "OFF"}</strong>. It runs only while the shop is running.
        Automatic limits: reorders up to <strong>{formatGBP(l.auto_reorder_max)}</strong> each and{" "}
        <strong>{formatGBP(l.auto_reorder_weekly_max)}</strong> per week; price rises up to{" "}
        <strong>{l.auto_price_max_pct}%</strong> (never lowers prices); minimum margin{" "}
        <strong>{Math.round(l.min_contribution_margin * 100)}%</strong>. Change them in <code>backend\.env</code>.
      </p>
      <div style={{ overflowX: "auto" }}>
      <table className="lines">
        <thead><tr><th>Job</th><th>Schedule</th><th>Last run</th><th>Result</th><th /></tr></thead>
        <tbody>
          {st.jobs.map((j) => (
            <tr key={j.job} data-testid={`job-${j.job}`}>
              <td>{j.job.replaceAll("_", " ")}</td>
              <td>{j.schedule}</td>
              <td>{when(j.last_run)}</td>
              <td style={{ overflowWrap: "anywhere", minWidth: 160 }}><strong>{j.last_status ?? "—"}</strong> {j.last_message}</td>
              <td><button className="btn secondary" style={{ whiteSpace: "nowrap" }} disabled={busy !== ""} onClick={() => runNow(j.job)}>
                {busy === j.job ? "Running…" : "Run now"}</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      <h2>Latest daily report</h2>
      {report?.content
        ? <pre className="panel" style={{ whiteSpace: "pre-wrap" }} data-testid="report">{report.content}</pre>
        : <p className="muted">No report yet. Click “Run now” on <em>daily report</em>.</p>}
    </div>
  );
}

export function PurchaseOrdersTab({ call, onError }: { call: Call; onError: (m: string) => void }) {
  const [pos, setPos] = useState<PO[]>([]);
  const load = useCallback(() => call<PO[]>("purchase-orders").then(setPos).catch((e: Error) => onError(e.message)), [call, onError]);
  useEffect(() => { load(); }, [load]);

  async function setStatus(id: number, status: string) {
    if (status === "received" && !window.confirm("Mark as received? This adds the quantity to stock.")) return;
    try { await call(`purchase-orders/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }); await load(); }
    catch (e) { onError((e as Error).message); }
  }

  if (pos.length === 0) return <p className="muted">No purchase orders yet. They appear here when stock runs low.</p>;
  return (
    <div style={{ overflowX: "auto" }}>
    <table className="lines" data-testid="purchase-orders">
      <thead><tr><th>#</th><th>Created</th><th>Product</th><th className="num">Qty</th><th className="num">Total (est.)</th><th>Status</th><th /></tr></thead>
      <tbody>
        {pos.map((po) => (
          <tr key={po.id}>
            <td>{po.id}</td>
            <td>{when(po.created_at)}</td>
            <td>{po.product_id}</td>
            <td className="num">{po.quantity}</td>
            <td className="num">{formatGBP(po.total)}</td>
            <td><strong>{po.status === "approved" ? "ready to send" : po.status}</strong></td>
            <td>{po.next_statuses.map((s) => (
              <button key={s} className="btn secondary" style={{ margin: 2, padding: "4px 10px" }} onClick={() => setStatus(po.id, s)}>
                Mark {s}
              </button>
            ))}</td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}
