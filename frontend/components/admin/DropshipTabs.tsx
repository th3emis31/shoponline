"use client";

import { useCallback, useEffect, useState } from "react";
import { formatGBP } from "@/lib/money";

type Call = <T>(path: string, init?: RequestInit) => Promise<T>;

export type AdminProduct = {
  id: string; name: string; price: number; stock: number; active: boolean; landed_cost: number;
  contribution_pre_ads: number; contribution_margin: number; break_even_roas: number | null;
  fulfilment: "stock" | "dropship"; supplier_name: string; supplier_url: string;
  supplier_cost: number; delivery_estimate: string;
};

type SupplierOrder = {
  id: number; order_id: string; product_id: string; quantity: number; supplier_name: string;
  supplier_url: string; supplier_cost_total: number; sale_total: number; profit_estimate: number;
  status: string; supplier_ref: string; tracking: string; note: string; created_at: string;
  next_statuses: string[]; ship_to_name: string; ship_to_address: string;
};

const pct = (x: number | null) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);
const safeLink = (u: string) => /^https?:\/\//i.test(u); // never render javascript: etc.

const STATUS_LABEL: Record<string, string> = {
  to_order: "To order", ordered: "Ordered", shipped: "Shipped", delivered: "Delivered", problem: "Problem",
};

/** One product's settings: price, visibility, and either own stock or dropship supplier. */
export function ProductForm({ p, onSave }: { p: AdminProduct; onSave: (id: string, form: HTMLFormElement) => void }) {
  const [mode, setMode] = useState<"stock" | "dropship">(p.fulfilment);
  return (
    <form className="panel stack" data-testid={`product-${p.id}`}
          onSubmit={(e) => { e.preventDefault(); onSave(p.id, e.currentTarget); }}>
      <strong>{p.name}</strong>
      <div className="muted" style={{ fontSize: "0.9rem" }}>
        Contribution before ads: <strong>{formatGBP(p.contribution_pre_ads)}</strong> ({pct(p.contribution_margin)})<br />
        Break-even ROAS: <strong data-testid="roas">{p.break_even_roas == null ? "never profitable" : p.break_even_roas.toFixed(2)}</strong>
        <br /><em>ESTIMATE until supplier quotes</em>
      </div>
      <label>Price inc. VAT (£)<input name="price" type="number" step="0.01" min="0.01" defaultValue={(p.price / 100).toFixed(2)} /></label>
      <label>How it&apos;s fulfilled
        {/* aria-label: otherwise the option texts become part of the field's name */}
        <select name="fulfilment" aria-label="How it's fulfilled" value={mode}
                onChange={(e) => setMode(e.target.value as "stock" | "dropship")}>
          <option value="stock">My own stock</option>
          <option value="dropship">Dropship (supplier ships to the customer)</option>
        </select>
      </label>
      {mode === "stock" ? (
        <>
          <label>Landed cost (£)<input name="landed_cost" type="number" step="0.01" min="0" defaultValue={(p.landed_cost / 100).toFixed(2)} /></label>
          <label>Stock<input name="stock" type="number" min="0" step="1" defaultValue={p.stock} /></label>
        </>
      ) : (
        <>
          <label>Supplier name<input name="supplier_name" maxLength={200} defaultValue={p.supplier_name} /></label>
          <label>Supplier product link<input name="supplier_url" type="url" maxLength={1000} placeholder="https://" defaultValue={p.supplier_url} /></label>
          <label>Supplier price per unit, incl. delivery to customer (£)
            <input name="supplier_cost" type="number" step="0.01" min="0" defaultValue={(p.supplier_cost / 100).toFixed(2)} />
          </label>
        </>
      )}
      <label>Delivery time shown to customers<input name="delivery_estimate" maxLength={100} placeholder="e.g. 7-12 working days" defaultValue={p.delivery_estimate} /></label>
      <label style={{ display: "flex", gap: 8, alignItems: "center" }}><input name="active" type="checkbox" defaultChecked={p.active} /> Visible in shop</label>
      <label>Reason for change (audit log)<input name="note" maxLength={500} /></label>
      <button className="btn" type="submit">Save</button>
    </form>
  );
}

/** Paid dropship lines: what to buy from which supplier, shipped to whom, and the profit. */
export function SupplierOrdersTab({ call, onError }: { call: Call; onError: (m: string) => void }) {
  const [rows, setRows] = useState<SupplierOrder[]>([]);
  const load = useCallback(() => call<SupplierOrder[]>("supplier-orders").then(setRows).catch((e: Error) => onError(e.message)), [call, onError]);
  useEffect(() => { load(); }, [load]);

  async function update(id: number, body: Record<string, string>) {
    try { await call(`supplier-orders/${id}`, { method: "POST", body: JSON.stringify(body) }); await load(); }
    catch (e) { onError((e as Error).message); }
  }

  function advance(so: SupplierOrder, status: string) {
    const ask: Record<string, string> = {
      ordered: "Supplier's order number (optional):",
      shipped: "Tracking number (optional):",
      problem: "What went wrong?",
    };
    let body: Record<string, string> = { status };
    if (ask[status]) {
      const v = window.prompt(ask[status], "");
      if (v === null) return;
      if (status === "ordered" && v) body = { ...body, supplier_ref: v };
      if (status === "shipped" && v) body = { ...body, tracking: v };
      if (status === "problem" && v) body = { ...body, note: v };
    }
    update(so.id, body);
  }

  const todo = rows.filter((r) => r.status === "to_order");
  const profit = rows.reduce((n, r) => n + r.profit_estimate, 0);
  if (rows.length === 0) {
    return <p className="muted">No supplier orders yet. They appear here when a customer pays for a dropship product.</p>;
  }
  return (
    <div data-testid="supplier-orders">
      <p className="notice">
        <strong>{todo.length}</strong> to order now. Estimated profit on these orders: <strong>{formatGBP(profit)}</strong>.
        Buy from the supplier using the customer&apos;s delivery address, then record the supplier&apos;s order number.
      </p>
      <div style={{ overflowX: "auto" }}>
        <table className="lines">
          <thead><tr><th>Product</th><th>Ship to</th><th>Supplier</th><th className="num">You pay</th><th className="num">Customer paid</th><th className="num">Profit (est.)</th><th>Status</th><th /></tr></thead>
          <tbody>
            {rows.map((so) => (
              <tr key={so.id} data-testid={`so-${so.id}`}>
                <td>{so.product_id} × {so.quantity}</td>
                <td>{so.ship_to_name}<br /><span className="muted small">{so.ship_to_address}</span></td>
                <td>
                  {safeLink(so.supplier_url)
                    ? <a href={so.supplier_url} target="_blank" rel="noopener noreferrer">{so.supplier_name || "Open supplier"}</a>
                    : (so.supplier_name || <span className="error">No supplier link set</span>)}
                  {so.supplier_ref && <><br /><span className="muted small">Ref {so.supplier_ref}</span></>}
                  {so.tracking && <><br /><span className="muted small">Tracking {so.tracking}</span></>}
                </td>
                <td className="num">{formatGBP(so.supplier_cost_total)}</td>
                <td className="num">{formatGBP(so.sale_total)}</td>
                <td className="num"><strong>{formatGBP(so.profit_estimate)}</strong></td>
                <td><strong>{STATUS_LABEL[so.status] ?? so.status}</strong>{so.note && <><br /><span className="muted small">{so.note}</span></>}</td>
                <td>{so.next_statuses.map((s) => (
                  <button key={s} className="btn secondary" style={{ margin: 2, padding: "4px 10px", whiteSpace: "nowrap" }} onClick={() => advance(so, s)}>
                    {STATUS_LABEL[s] ?? s}
                  </button>
                ))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
