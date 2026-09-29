"use client";

import { useCallback, useEffect, useState } from "react";

type Call = <T>(path: string, init?: RequestInit) => Promise<T>;
type Row = {
  id: number; order_id: string; product: string; rating: number; title: string; body: string; name: string;
  status: "pending" | "published" | "rejected"; reject_reason: string; created_at: string;
};
type Data = { reasons: Record<string, string>; reviews: Row[] };

/** Check verified-buyer reviews. Publish every genuine one; reject only for a listed reason. */
export default function ReviewsTab({ call, onError }: { call: Call; onError: (m: string) => void }) {
  const [data, setData] = useState<Data | null>(null);
  const load = useCallback(() => call<Data>("reviews").then(setData).catch((e: Error) => onError(e.message)), [call, onError]);
  useEffect(() => { load(); }, [load]);

  async function act(id: number, action: "publish" | "reject", reason = "") {
    try {
      await call(`reviews/${id}`, { method: "POST", body: JSON.stringify({ action, reason }) });
      await load();
    } catch (e) { onError((e as Error).message); }
  }

  if (!data) return <p>Loading…</p>;
  const pending = data.reviews.filter((r) => r.status === "pending").length;
  return (
    <div data-testid="reviews-admin">
      <p className="notice">
        <strong>{pending}</strong> waiting. Publish every genuine review, <strong>including negative ones</strong>.
        UK law (DMCC Act 2024) forbids hiding reviews for being critical. Reject only for one of the listed reasons.
      </p>
      {data.reviews.length === 0 ? <p className="muted">No reviews yet. Buyers get a review link in their order email and on their order page.</p> : (
        <div style={{ overflowX: "auto" }}>
          <table className="lines">
            <thead><tr><th>Product</th><th>Rating</th><th>Review</th><th>Status</th><th /></tr></thead>
            <tbody>
              {data.reviews.map((r) => (
                <tr key={r.id} data-testid={`review-row-${r.id}`}>
                  <td>{r.product}</td>
                  <td>{r.rating}/5</td>
                  <td>{r.title && <strong>{r.title}<br /></strong>}{r.body}<br /><span className="muted small">{r.name}</span></td>
                  <td>{r.status}{r.reject_reason && <><br /><span className="muted small">{data.reasons[r.reject_reason] ?? r.reject_reason}</span></>}</td>
                  <td>
                    {r.status !== "published" && <button className="btn secondary" onClick={() => act(r.id, "publish")}>Publish</button>}{" "}
                    {r.status !== "rejected" && (
                      <select aria-label={`Reject review ${r.id}`} defaultValue="" onChange={(e) => e.target.value && act(r.id, "reject", e.target.value)}>
                        <option value="">Reject for…</option>
                        {Object.entries(data.reasons).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
