"use client";

import { useCallback, useEffect, useState } from "react";
import { ApprovalsTab, AutomationTab, PurchaseOrdersTab } from "@/components/admin/AutomationTabs";
import { formatGBP } from "@/lib/money";

const TOKEN_KEY = "novahaus.adminToken";
type Tab = "orders" | "approvals" | "automation" | "purchase-orders" | "products" | "funnel" | "audit";
const TAB_LABEL: Record<Tab, string> = {
  orders: "Orders", approvals: "Approvals", automation: "Automation", "purchase-orders": "Purchase orders",
  products: "Products", funnel: "Funnel", audit: "Audit",
};

type AdminOrder = {
  id: string; status: string; total: number; created_at: string; customer_name: string;
  customer_email: string; shipping_address: string; next_statuses: string[];
  items: { name: string; quantity: number }[];
};
type AdminProduct = {
  id: string; name: string; price: number; stock: number; active: boolean; landed_cost: number;
  shipping_cost: number; packaging_cost: number; contribution_pre_ads: number;
  contribution_margin: number; break_even_roas: number | null;
};
type Funnel = { days: number; steps: { type: string; count: number; rate_from_previous: number | null }[]; overall_conversion: number | null };
type Audit = { id: number; action: string; target: string; actor: string | null; detail: Record<string, unknown>; created_at: string };

function session(): Storage | null {
  try { return window.sessionStorage; } catch { return null; }
}

const pct = (x: number | null) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [me, setMe] = useState<{ actor: string; role: string } | null>(null);
  const [useSharedToken, setUseSharedToken] = useState(false);
  const [tab, setTab] = useState<Tab>("orders");
  const [error, setError] = useState("");
  const [orders, setOrders] = useState<AdminOrder[]>([]);
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [funnel, setFunnel] = useState<Funnel | null>(null);
  const [audit, setAudit] = useState<Audit[]>([]);

  useEffect(() => { setToken(session()?.getItem(TOKEN_KEY) ?? ""); }, []);

  const call = useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    const res = await fetch(`/admin-api/${path}`, {
      ...init, headers: { "Content-Type": "application/json", "X-Admin-Token": token },
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 || res.status === 503) {
      session()?.removeItem(TOKEN_KEY);
      setToken("");
      throw new Error(data.detail ?? "Not authorised");
    }
    if (!res.ok) throw new Error(data.error ?? data.detail?.[0]?.msg ?? data.detail ?? "Request failed");
    return data as T;
  }, [token]);

  const load = useCallback(async () => {
    if (!token) return;
    setError("");
    try {
      if (tab === "orders") setOrders(await call<AdminOrder[]>("orders"));
      if (tab === "products") setProducts(await call<AdminProduct[]>("products"));
      if (tab === "funnel") setFunnel(await call<Funnel>("funnel?days=30"));
      if (tab === "audit") setAudit(await call<Audit[]>("audit"));
    } catch (err) {
      setError((err as Error).message);
    }
  }, [tab, token, call]);

  useEffect(() => {
    if (!token) { setMe(null); return; }
    call<{ actor: string; role: string }>("me").then(setMe).catch((err: Error) => setError(err.message));
  }, [token, call]);

  useEffect(() => { if (me) load(); }, [load, me]);

  async function signIn(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setError("");
    if (useSharedToken) {
      const t = String(f.get("token") ?? "");
      session()?.setItem(TOKEN_KEY, t);
      setToken(t);
      return;
    }
    const res = await fetch("/admin-api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: f.get("email"), password: f.get("password") }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { setError(data.detail ?? "Sign-in failed"); return; }
    session()?.setItem(TOKEN_KEY, data.token);
    setToken(data.token);
  }

  async function signOut() {
    await fetch("/admin-api/logout", { method: "POST", headers: { "X-Admin-Token": token } }).catch(() => {});
    session()?.removeItem(TOKEN_KEY);
    setToken("");
    setMe(null);
    setTab("orders");
  }

  const tabs: Tab[] = me?.role === "owner"
    ? ["orders", "approvals", "automation", "purchase-orders", "products", "funnel", "audit"]
    : ["orders"];

  async function changeStatus(id: string, status: string) {
    const note = window.prompt(`Change order to "${status}". Optional note (e.g. tracking number):`, "");
    if (note === null) return;
    try {
      await call(`orders/${id}/status`, { method: "POST", body: JSON.stringify({ status, note }) });
      await load();
    } catch (err) { setError((err as Error).message); }
  }

  async function saveProduct(id: string, form: HTMLFormElement) {
    const f = new FormData(form);
    const num = (k: string) => Math.round(Number(f.get(k)));
    const pounds = (k: string) => Math.round(Number(f.get(k)) * 100);
    const body = {
      stock: num("stock"), price: pounds("price"), active: f.get("active") === "on",
      landed_cost: pounds("landed_cost"), note: String(f.get("note") ?? ""),
    };
    try {
      await call(`products/${id}`, { method: "PATCH", body: JSON.stringify(body) });
      await load();
    } catch (err) { setError((err as Error).message); }
  }

  if (!token || !me) {
    return (
      <>
        <h1>Admin</h1>
        <form className="stack" onSubmit={signIn}>
          {useSharedToken ? (
            <label>Shared admin token (ADMIN_TOKEN in backend/.env)<input name="token" type="password" required autoComplete="off" /></label>
          ) : (
            <>
              <label>Email<input name="email" type="email" required autoComplete="username" /></label>
              <label>Password<input name="password" type="password" required autoComplete="current-password" /></label>
            </>
          )}
          <button className="btn" type="submit">Sign in</button>
          <button type="button" className="btn link" style={{ color: "var(--muted)", justifySelf: "start" }}
                  onClick={() => { setUseSharedToken(!useSharedToken); setError(""); }}>
            {useSharedToken ? "Sign in with email and password" : "Use the shared admin token instead"}
          </button>
          {error && <p className="error">{error}</p>}
        </form>
      </>
    );
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <h1>Admin</h1>
        <div>
          <span className="muted" data-testid="whoami">{me.actor} · {me.role}</span>{" "}
          <button className="btn secondary" onClick={signOut}>Sign out</button>
        </div>
      </div>
      <nav className="main" aria-label="Admin sections" style={{ marginBottom: 20 }}>
        {tabs.map((t) => (
          <button key={t} className={t === tab ? "btn" : "btn secondary"} onClick={() => setTab(t)}>
            {TAB_LABEL[t]}
          </button>
        ))}
      </nav>
      {error && <p className="error" data-testid="admin-error">{error}</p>}

      {tab === "approvals" && <ApprovalsTab call={call} onError={setError} />}
      {tab === "automation" && <AutomationTab call={call} onError={setError} />}
      {tab === "purchase-orders" && <PurchaseOrdersTab call={call} onError={setError} />}

      {tab === "orders" && (
        orders.length === 0 ? <p>No orders yet.</p> : (
          <div style={{ overflowX: "auto" }}>
            <table className="lines" data-testid="orders">
              <thead><tr><th>Date</th><th>Customer</th><th>Items</th><th className="num">Total</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id}>
                    <td>{new Date(o.created_at).toLocaleString("en-GB")}</td>
                    <td>{o.customer_name}<br /><span className="muted">{o.customer_email}</span><br /><span className="muted">{o.shipping_address}</span></td>
                    <td>{o.items.map((i) => `${i.name} × ${i.quantity}`).join(", ")}</td>
                    <td className="num">{formatGBP(o.total)}</td>
                    <td><strong>{o.status}</strong></td>
                    <td>
                      {o.next_statuses.length === 0 && <span className="muted">—</span>}
                      {o.next_statuses.map((s) => (
                        <button key={s} className="btn secondary" style={{ margin: 2, padding: "4px 10px" }} onClick={() => changeStatus(o.id, s)}>
                          Mark {s}
                        </button>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {tab === "products" && (
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
          {products.map((p) => (
            // Key includes the values: when fresh data arrives the form is rebuilt, so it can
            // never show (and then save back) stale numbers.
            <form key={`${p.id}:${p.price}:${p.landed_cost}:${p.stock}:${p.active}`} className="panel stack" data-testid={`product-${p.id}`}
                  onSubmit={(e) => { e.preventDefault(); saveProduct(p.id, e.currentTarget); }}>
              <strong>{p.name}</strong>
              <div className="muted" style={{ fontSize: "0.9rem" }}>
                Contribution before ads: <strong>{formatGBP(p.contribution_pre_ads)}</strong> ({pct(p.contribution_margin)})<br />
                Break-even ROAS: <strong data-testid="roas">{p.break_even_roas == null ? "never profitable" : p.break_even_roas.toFixed(2)}</strong>
                <br /><em>ESTIMATE until supplier quotes</em>
              </div>
              <label>Price inc. VAT (£)<input name="price" type="number" step="0.01" min="0.01" defaultValue={(p.price / 100).toFixed(2)} /></label>
              <label>Landed cost (£)<input name="landed_cost" type="number" step="0.01" min="0" defaultValue={(p.landed_cost / 100).toFixed(2)} /></label>
              <label>Stock<input name="stock" type="number" min="0" step="1" defaultValue={p.stock} /></label>
              <label style={{ display: "flex", gap: 8, alignItems: "center" }}><input name="active" type="checkbox" defaultChecked={p.active} /> Visible in shop</label>
              <label>Reason for change (audit log)<input name="note" maxLength={500} /></label>
              <button className="btn" type="submit">Save</button>
            </form>
          ))}
        </div>
      )}

      {tab === "funnel" && funnel && (
        <>
          <p className="muted">Last {funnel.days} days. Anonymous counts only: no cookies, no personal data.</p>
          <table className="lines" data-testid="funnel">
            <thead><tr><th>Step</th><th className="num">Count</th><th className="num">From previous step</th></tr></thead>
            <tbody>
              {funnel.steps.map((s) => (
                <tr key={s.type}><td>{s.type.replace("_", " ")}</td><td className="num">{s.count}</td><td className="num">{pct(s.rate_from_previous)}</td></tr>
              ))}
            </tbody>
          </table>
          <p>Overall conversion (product view → purchase): <strong>{pct(funnel.overall_conversion)}</strong></p>
        </>
      )}

      {tab === "audit" && (
        audit.length === 0 ? <p>No admin changes yet.</p> : (
          <table className="lines" data-testid="audit">
            <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id}>
                  <td>{new Date(a.created_at).toLocaleString("en-GB")}</td>
                  <td>{a.actor ?? "—"}</td>
                  <td>{a.action}</td>
                  <td>{a.target}</td>
                  <td><code style={{ fontSize: "0.8rem" }}>{JSON.stringify(a.detail)}</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}
    </>
  );
}
