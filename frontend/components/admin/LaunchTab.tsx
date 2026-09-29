"use client";

import { useCallback, useEffect, useState } from "react";

type Call = <T>(path: string, init?: RequestInit) => Promise<T>;
type Gate = {
  id: string; name: string; condition: string; label: string; needs_owner: boolean; checks: { ok: boolean; text: string }[];
  confirmed: boolean; value: string; note: string; confirmed_by: string | null; passed: boolean;
};
type Data = { green: number; total: number; ready: boolean; gates: Gate[] };

function GateRow({ g, save }: { g: Gate; save: (id: string, confirmed: boolean, value: string, note: string) => Promise<void> }) {
  const [note, setNote] = useState(g.note);
  const [value, setValue] = useState(g.value);
  return (
    <section className="panel" data-testid={`gate-${g.id}`} style={{ marginBottom: 12, borderLeft: `4px solid ${g.passed ? "var(--good)" : "var(--danger)"}` }}>
      <p>
        <strong>{g.passed ? "✅" : "⬜"} {g.name}</strong>{g.label && <span className="badge" style={{ marginLeft: 8 }}>{g.label}</span>}
        <br /><span className="small muted">{g.condition}</span>
      </p>
      <ul className="small" style={{ margin: "4px 0 8px" }}>
        {g.checks.map((c, i) => <li key={i}>{c.ok ? "✓" : "✗"} {c.text}</li>)}
      </ul>
      {g.needs_owner && (
        <div className="stack">
          {g.id === "website" && (
            <label>Mobile Lighthouse performance score (0 to 100)
              <input type="number" min={0} max={100} value={value} onChange={(e) => setValue(e.target.value)} />
            </label>
          )}
          <label>Evidence / note<input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} placeholder="e.g. quote from Supplier A, 12 Oct" /></label>
          <p>
            {g.confirmed
              ? <button className="btn link" onClick={() => save(g.id, false, value, note)}>Undo my confirmation</button>
              : <button className="btn secondary" onClick={() => save(g.id, true, value, note)}>I confirm this is done</button>}
            {g.confirmed_by && <span className="small muted"> Confirmed by {g.confirmed_by}</span>}
          </p>
        </div>
      )}
    </section>
  );
}

/** Owner only: the blueprint's 14 launch gates. The shop launches only when all are green. */
export default function LaunchTab({ call, onError }: { call: Call; onError: (m: string) => void }) {
  const [data, setData] = useState<Data | null>(null);
  const load = useCallback(() => call<Data>("launch").then(setData).catch((e: Error) => onError(e.message)), [call, onError]);
  useEffect(() => { load(); }, [load]);
  async function save(id: string, confirmed: boolean, value: string, note: string) {
    try { setData(await call<Data>(`launch/${id}`, { method: "POST", body: JSON.stringify({ confirmed, value, note }) })); } catch (e) { onError((e as Error).message); }
  }
  if (!data) return <p>Loading…</p>;
  return (
    <div data-testid="launch">
      <p className="notice">
        <strong data-testid="launch-score">{data.green} of {data.total}</strong> launch gates are green.{" "}
        {data.ready
          ? <>Everything is green: you can set <code>LAUNCH_READY=true</code> (see DEPLOY.md, step 7).</>
          : <>The blueprint says: launch only when every gate is green. A working website is one gate of fourteen.</>}
        <br />
        <span className="small">Measure mobile speed free at pagespeed.web.dev with your live shop address, then enter the score under Website.</span>
      </p>
      {data.gates.map((g) => <GateRow key={`${g.id}-${g.confirmed}-${g.value}`} g={g} save={save} />)}
    </div>
  );
}
