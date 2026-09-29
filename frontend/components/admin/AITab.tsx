"use client";

import { useCallback, useEffect, useState } from "react";

type Call = <T>(path: string, init?: RequestInit) => Promise<T>;
type Task = { id: number; agent: string; subject: string; provider: string; output: string; status: string; error: string; created_by: string | null; decided_by: string | null; created_at: string };
type Decision = { id: number; title: string; decision: string; reason: string; evidence: string; decided_by: string | null; created_at: string };
type Overview = {
  provider: string; model: string; calls_today: number; daily_limit: number; agents: Record<string, string>;
  needs_product: string[]; tasks: Task[]; decisions: Decision[];
};

const PROVIDER_TEXT: Record<string, string> = {
  rules: "Built-in rules (free, no AI service). For a free local AI model, install Ollama and set AI_PROVIDER=ollama.",
  ollama: "Local AI model on this computer (free).",
  api: "External AI service (paid). Personal details are removed before sending.",
};

function Output({ text }: { text: string }) {
  return (
    <div className="ai-output">
      {text.split("\n").map((line, i) => {
        const label = line.match(/^(FACT|ASSUMPTION|ESTIMATE|HYPOTHESIS)/)?.[1];
        return <div key={i} className={label ? `ai-line ai-${label.toLowerCase()}` : "ai-line"}>{line}</div>;
      })}
    </div>
  );
}

/** Owner only: the seven assistants. Their output is advice to approve or reject; nothing is applied automatically. */
export default function AITab({ call, onError }: { call: Call; onError: (m: string) => void }) {
  const [data, setData] = useState<Overview | null>(null);
  const [products, setProducts] = useState<{ id: string; name: string }[]>([]);
  const [agent, setAgent] = useState("analytics");
  const [subject, setSubject] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => call<Overview>("ai").then(setData).catch((e: Error) => onError(e.message)), [call, onError]);
  useEffect(() => {
    load();
    call<{ id: string; name: string }[]>("products").then((p) => { setProducts(p); if (p[0]) setSubject(p[0].id); }).catch(() => {});
  }, [load, call]);

  async function run() {
    setBusy(true);
    try {
      const needs = data?.needs_product.includes(agent);
      await call("ai/run", { method: "POST", body: JSON.stringify({ agent, subject: needs ? subject : "" }) });
      await load();
    } catch (e) { onError((e as Error).message); } finally { setBusy(false); }
  }
  async function decide(id: number, approve: boolean) {
    const note = window.prompt(approve ? "Why do you agree? (optional)" : "Why not? (optional)", "");
    if (note === null) return;
    try { await call(`ai/${id}/decide`, { method: "POST", body: JSON.stringify({ approve, note }) }); await load(); } catch (e) { onError((e as Error).message); }
  }
  async function addDecision(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await call("decisions", { method: "POST", body: JSON.stringify({ title: f.get("title"), decision: f.get("decision"), reason: f.get("reason"), evidence: f.get("evidence") }) });
      form.reset();
      await load();
    } catch (err) { onError((err as Error).message); }
  }

  if (!data) return <p>Loading…</p>;
  const needsProduct = data.needs_product.includes(agent);
  return (
    <div data-testid="ai">
      <p className="notice">
        <strong>{PROVIDER_TEXT[data.provider] ?? data.provider}</strong>
        {data.provider !== "rules" && <> Model: {data.model || "—"} · calls today {data.calls_today}/{data.daily_limit}.</>}
        <br />
        Every line is labelled <span className="ai-fact">FACT</span>, <span className="ai-assumption">ASSUMPTION</span>,{" "}
        <span className="ai-estimate">ESTIMATE</span> or <span className="ai-hypothesis">HYPOTHESIS</span>. Assistants only advise:
        approving records your decision; it never changes prices, stock or orders.
      </p>
      <div className="stack" style={{ maxWidth: 520 }}>
        <label>Assistant
          <select value={agent} onChange={(e) => setAgent(e.target.value)}>
            {Object.entries(data.agents).filter(([k]) => k !== "customer").map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        {needsProduct && (
          <label>Product
            <select value={subject} onChange={(e) => setSubject(e.target.value)}>
              {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
        )}
        <p><button className="btn" onClick={run} disabled={busy}>{busy ? "Thinking…" : "Ask the assistant"}</button></p>
        <p className="small muted">Customer-reply drafts are in the Support tab.</p>
      </div>

      <h2>Drafts and results</h2>
      {data.tasks.length === 0 && <p className="muted">Nothing yet.</p>}
      {data.tasks.map((t) => (
        <section key={t.id} className="panel" data-testid={`ai-task-${t.id}`} style={{ marginBottom: 12 }}>
          <p className="small">
            <strong>#{t.id} {data.agents[t.agent]?.split(":")[0] ?? t.agent}</strong>{t.subject && <> · {t.subject}</>} · {t.provider} ·{" "}
            <strong>{t.status}</strong>{t.decided_by && <> by {t.decided_by}</>}
          </p>
          <Output text={t.output} />
          {t.status === "draft" && (
            <p>
              <button className="btn secondary" onClick={() => decide(t.id, true)}>Approve</button>{" "}
              <button className="btn link" onClick={() => decide(t.id, false)}>Reject</button>
            </p>
          )}
        </section>
      ))}

      <h2>Decision log</h2>
      <form className="stack" onSubmit={addDecision} style={{ maxWidth: 520 }}>
        <label>Decision title<input name="title" required minLength={3} maxLength={200} /></label>
        <label>What was decided<textarea name="decision" required minLength={3} rows={2} /></label>
        <label>Why (optional)<input name="reason" maxLength={2000} /></label>
        <label>Evidence (optional)<input name="evidence" maxLength={2000} /></label>
        <button className="btn secondary" type="submit">Add to decision log</button>
      </form>
      <div style={{ overflowX: "auto" }}>
        <table className="lines">
          <thead><tr><th>When</th><th>Decision</th><th>Why</th><th>By</th></tr></thead>
          <tbody>
            {data.decisions.map((d) => (
              <tr key={d.id}>
                <td className="small">{new Date(d.created_at).toLocaleDateString("en-GB")}</td>
                <td><strong>{d.title}</strong><br /><span className="small" style={{ whiteSpace: "pre-wrap" }}>{d.decision.slice(0, 400)}</span></td>
                <td className="small">{d.reason}{d.evidence && <><br /><span className="muted">{d.evidence}</span></>}</td>
                <td className="small">{d.decided_by}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
