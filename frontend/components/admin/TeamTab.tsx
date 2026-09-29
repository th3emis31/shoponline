"use client";

import { useCallback, useEffect, useState } from "react";

type Call = <T>(path: string, init?: RequestInit) => Promise<T>;
type User = { email: string; role: "owner" | "staff"; active: boolean; created_at: string };

/** Owner-only: add people, disable them, reset passwords. No command line needed. */
export default function TeamTab({ call, onError, me }: { call: Call; onError: (m: string) => void; me: string }) {
  const [users, setUsers] = useState<User[]>([]);
  const [done, setDone] = useState("");
  const load = useCallback(() => call<User[]>("users").then(setUsers).catch((e: Error) => onError(e.message)), [call, onError]);
  useEffect(() => { load(); }, [load]);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setDone("");
    try {
      await call("users", {
        method: "POST",
        body: JSON.stringify({ email: f.get("email"), password: f.get("password"), role: f.get("role") }),
      });
      form.reset();
      setDone(`Added ${String(f.get("email"))}.`);
      await load();
    } catch (err) { onError((err as Error).message); }
  }

  async function setActive(u: User, active: boolean) {
    try { await call(`users/${encodeURIComponent(u.email)}/active`, { method: "POST", body: JSON.stringify({ active }) }); await load(); }
    catch (err) { onError((err as Error).message); }
  }

  async function resetPassword(u: User) {
    const password = window.prompt(`New password for ${u.email} (at least 12 characters):`, "");
    if (!password) return;
    try {
      await call(`users/${encodeURIComponent(u.email)}/password`, { method: "POST", body: JSON.stringify({ password }) });
      setDone(`Password changed for ${u.email}; they were signed out everywhere.`);
    } catch (err) { onError((err as Error).message); }
  }

  return (
    <div data-testid="team">
      {me === "admin-token" && (
        <p className="notice">
          You&apos;re signed in with the shared setup token. Create your own <strong>owner</strong> login below.
          After that, the shared token stops working (safer) and you sign in with your email and password.
        </p>
      )}
      <form className="panel stack" onSubmit={add} style={{ maxWidth: 520 }}>
        <strong>Add a person</strong>
        <label>Email<input name="email" type="email" required autoComplete="off" /></label>
        <label>Password (at least 12 characters)<input name="password" type="password" required minLength={12} autoComplete="new-password" /></label>
        <label>Role
          <select name="role" aria-label="Role" defaultValue="staff">
            <option value="owner">Owner: everything</option>
            <option value="staff">Staff: orders only</option>
          </select>
        </label>
        <button className="btn" type="submit">Add</button>
        {done && <p className="notice" role="status">{done}</p>}
      </form>
      <h2>People</h2>
      {users.length === 0 ? <p className="muted">No personal logins yet.</p> : (
        <div style={{ overflowX: "auto" }}>
          <table className="lines">
            <thead><tr><th>Email</th><th>Role</th><th>Status</th><th /></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.email}>
                  <td>{u.email}{u.email === me && <span className="muted"> (you)</span>}</td>
                  <td>{u.role}</td>
                  <td>{u.active ? "active" : "disabled"}</td>
                  <td>
                    <button className="btn secondary" style={{ margin: 2, padding: "4px 10px" }} onClick={() => resetPassword(u)}>Reset password</button>
                    {u.email !== me && (
                      <button className="btn secondary" style={{ margin: 2, padding: "4px 10px" }} onClick={() => setActive(u, !u.active)}>
                        {u.active ? "Disable" : "Enable"}
                      </button>
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
