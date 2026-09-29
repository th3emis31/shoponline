"use client";

import { useCallback, useEffect, useState } from "react";
import { formatGBP } from "@/lib/money";

type Call = <T>(path: string, init?: RequestInit) => Promise<T>;
type Row = {
  campaign: string; spend: number; clicks: number; impressions: number; visits: number; orders: number; revenue: number;
  contribution_pre_ads: number; contribution_after_ads: number; ctr: number | null; cpc: number | null;
  cac: number | null; roas: number | null; verdict: string;
};
type Spend = { id: number; campaign: string; day: string; spend: number; clicks: number; impressions: number; note: string; created_by: string | null };
type Report = { days: number; label: string; campaigns: Row[]; totals: Record<string, number>; spend_rows: Spend[] };

const money = (p: number | null) => (p == null ? "—" : formatGBP(p));
const pct = (x: number | null) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

/** Owner only: which ads make money after their own cost (Blueprint section I). */
export default function CampaignsTab({ call, onError }: { call: Call; onError: (m: string) => void }) {
  const [data, setData] = useState<Report | null>(null);
  const [days, setDays] = useState(30);
  const [note, setNote] = useState("");
  const load = useCallback(() => call<Report>(`campaigns?days=${days}`).then(setData).catch((e: Error) => onError(e.message)), [call, onError, days]);
  useEffect(() => { load(); }, [load]);

  async function addSpend(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const pounds = Number(f.get("spend"));
    if (!Number.isFinite(pounds) || pounds < 0) { onError("Enter the amount in pounds, e.g. 12.50"); return; }
    try {
      const r = await call<{ campaign: string }>("campaigns/spend", {
        method: "POST",
        body: JSON.stringify({
          campaign: String(f.get("campaign")), day: String(f.get("day")), spend: Math.round(pounds * 100),
          clicks: Number(f.get("clicks") || 0), impressions: Number(f.get("impressions") || 0), note: String(f.get("note") ?? ""),
        }),
      });
      setNote(`Saved ad cost for ${r.campaign}.`);
      form.reset();
      await load();
    } catch (err) { onError((err as Error).message); }
  }

  if (!data) return <p>Loading…</p>;
  return (
    <div data-testid="campaigns">
      <p className="notice">
        Put <code>?utm_source=facebook&amp;utm_campaign=desk-reset</code> on every ad link. Orders from that link are counted
        here as <strong>facebook:desk-reset</strong>. Type in what each ad cost, from the ad platform.
        Profit uses your product cost <strong>{data.label}S</strong> until the real supplier prices are in.
      </p>
      <p>
        <label>Period{" "}
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Period">
            <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option>
          </select>
        </label>
      </p>
      <div style={{ overflowX: "auto" }}>
        <table className="lines">
          <thead>
            <tr>
              <th>Campaign</th><th className="num">Ad cost</th><th className="num">CTR</th><th className="num">CPC</th>
              <th className="num">Visits</th><th className="num">Orders</th><th className="num">Revenue</th><th className="num">CAC</th>
              <th className="num">ROAS</th><th className="num">Profit after ads</th><th>What to do</th>
            </tr>
          </thead>
          <tbody>
            {data.campaigns.length === 0 && <tr><td colSpan={11} className="muted">No orders or ad costs in this period yet.</td></tr>}
            {data.campaigns.map((r) => (
              <tr key={r.campaign} data-testid={`campaign-${r.campaign}`}>
                <td>{r.campaign}</td>
                <td className="num">{money(r.spend)}</td>
                <td className="num">{pct(r.ctr)}</td>
                <td className="num">{money(r.cpc)}</td>
                <td className="num">{r.visits}</td>
                <td className="num">{r.orders}</td>
                <td className="num">{money(r.revenue)}</td>
                <td className="num">{money(r.cac)}</td>
                <td className="num">{r.roas == null ? "—" : `${r.roas.toFixed(2)}×`}</td>
                <td className="num"><strong className={r.contribution_after_ads < 0 ? "error" : ""}>{money(r.contribution_after_ads)}</strong></td>
                <td className="small">{r.verdict}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th>Total</th><th className="num">{money(data.totals.spend ?? 0)}</th><th /><th /><th />
              <th className="num">{data.totals.orders ?? 0}</th><th className="num">{money(data.totals.revenue ?? 0)}</th><th /><th />
              <th className="num">{money(data.totals.contribution_after_ads ?? 0)}</th><th />
            </tr>
          </tfoot>
        </table>
      </div>

      <h2>Add ad cost</h2>
      <form className="stack" onSubmit={addSpend} style={{ maxWidth: 480 }}>
        <label>Campaign tag (source:campaign)<input name="campaign" required placeholder="facebook:desk-reset" /></label>
        <label>Date<input name="day" type="date" required /></label>
        <label>Ad cost (£)<input name="spend" type="number" min="0" step="0.01" required /></label>
        <label>Clicks (optional)<input name="clicks" type="number" min="0" step="1" /></label>
        <label>Impressions (optional)<input name="impressions" type="number" min="0" step="1" /></label>
        <label>Note (optional)<input name="note" maxLength={200} /></label>
        <button className="btn" type="submit">Save ad cost</button>
        {note && <p role="status">{note}</p>}
      </form>

      {data.spend_rows.length > 0 && (
        <>
          <h2>Ad costs entered</h2>
          <div style={{ overflowX: "auto" }}>
            <table className="lines">
              <thead><tr><th>Date</th><th>Campaign</th><th className="num">Cost</th><th className="num">Clicks</th><th>Note</th></tr></thead>
              <tbody>
                {data.spend_rows.map((s) => (
                  <tr key={s.id}>
                    <td>{new Date(s.day).toLocaleDateString("en-GB")}</td><td>{s.campaign}</td>
                    <td className="num">{money(s.spend)}</td><td className="num">{s.clicks}</td><td className="small">{s.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
