"""Regression tests for the independent security/quality review.
Race conditions are reproduced by interleaving two database sessions by hand."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models import (AutomationRun, Cart, CartItem, JobLease, Order, Product, PurchaseOrder,
                        Recommendation)
from app.services import admin, auth, automation, orders, payments, shop

CUSTOMER = {"name": "Jane", "email": "jane@example.com", "address": "1 Main St"}


def stock(db, pid="monitor-riser"):
    with db() as s:
        return s.get(Product, pid).stock


def status(db, oid):
    with db() as s:
        return s.get(Order, oid).status


@pytest.fixture()
def stripe_on(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_x")
    monkeypatch.setattr(payments, "create_checkout_session", lambda order: (f"cs_{order.id}", "https://stripe.test"))
    monkeypatch.setattr(payments, "expire_session", lambda sid: None)


def pending_order(client, qty=2):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "monitor-riser", "quantity": qty})
    return client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER).json()


def event(oid, type_, eid, **obj):
    return {"id": eid, "type": type_, "data": {"object": {"id": f"cs_{oid}", "client_reference_id": oid, **obj}}}


# ---- High 1: stock released twice (cancelled -> payment_review -> cancelled)
def test_stock_never_released_twice(client, db, stripe_on):
    o = pending_order(client)
    assert stock(db) == 18
    with db() as s:
        payments.handle_event(s, event(o["id"], "checkout.session.expired", "e1"))
        payments.handle_event(s, event(o["id"], "checkout.session.completed", "e2", payment_status="paid",
                                       amount_total=o["total"], currency="gbp"))
    assert status(db, o["id"]) == "payment_review" and stock(db) == 20
    with db() as s:
        admin.set_order_status(s, o["id"], "cancelled", actor="owner")
    assert stock(db) == 20  # was 22 before the fix


# ---- High 2: accepting a reviewed late payment re-reserves stock
def test_accepting_reviewed_payment_reserves_stock(client, db, stripe_on):
    o = pending_order(client)
    with db() as s:
        payments.handle_event(s, event(o["id"], "checkout.session.expired", "e1"))
        payments.handle_event(s, event(o["id"], "checkout.session.completed", "e2", payment_status="paid",
                                       amount_total=o["total"], currency="gbp"))
        admin.set_order_status(s, o["id"], "paid", actor="owner")
    assert status(db, o["id"]) == "paid" and stock(db) == 18


def test_accepting_reviewed_payment_without_stock_is_refused(client, db, stripe_on):
    o = pending_order(client)
    with db() as s:
        payments.handle_event(s, event(o["id"], "checkout.session.expired", "e1"))
        payments.handle_event(s, event(o["id"], "checkout.session.completed", "e2", payment_status="paid",
                                       amount_total=o["total"], currency="gbp"))
        s.get(Product, "monitor-riser").stock = 1
        s.commit()
        with pytest.raises(shop.ShopError, match="Not enough stock"):
            admin.set_order_status(s, o["id"], "paid", actor="owner")
    assert status(db, o["id"]) == "payment_review" and stock(db) == 1  # nothing changed


# ---- High 3: concurrent cancel paths release stock once
def test_stale_reconcile_after_webhook_releases_once(client, db, stripe_on, monkeypatch):
    o = pending_order(client)
    a = db()
    stale = a.get(Order, o["id"])  # automation loaded the order...
    assert stale.status == "pending_payment"
    with db() as b:  # ...meanwhile the 'expired' webhook cancels it
        payments.handle_event(b, event(o["id"], "checkout.session.expired", "e1"))
    monkeypatch.setattr(payments, "retrieve_session", lambda sid: {"id": sid, "status": "expired", "payment_status": "unpaid"})
    stale.status = "pending_payment"  # stale in-memory view
    payments.reconcile_pending(a, stale)
    a.close()
    assert stock(db) == 20  # was 22 before the fix


# ---- High 4: receiving a purchase order never loses a concurrent sale
def test_po_receive_does_not_lose_concurrent_checkout(db):
    with db() as s:
        s.add(PurchaseOrder(product_id="desk-mat", quantity=20, unit_cost=600, total=12000, status="sent"))
        s.commit()
    a = db()
    a.get(Product, "desk-mat").stock  # loaded (50)
    with db() as b:  # a sale of 5 happens now
        c = shop.create_cart(b)
        shop.add_item(b, c.id, "desk-mat", 5)
        shop.checkout(b, c.id, "n", "e@example.com", "a")
    automation.set_po_status(a, 1, "received", "owner")
    a.close()
    assert stock(db, "desk-mat") == 65  # 50 - 5 + 20 (was 70 before the fix)


def test_po_double_receive_adds_stock_once(db):
    with db() as s:
        s.add(PurchaseOrder(product_id="desk-mat", quantity=20, unit_cost=600, total=12000, status="sent"))
        s.commit()
    a, b = db(), db()
    a.get(PurchaseOrder, 1).status, b.get(PurchaseOrder, 1).status  # both see "sent"
    automation.set_po_status(a, 1, "received", "owner")
    with pytest.raises(shop.ShopError):
        automation.set_po_status(b, 1, "received", "owner")
    a.close(); b.close()
    assert stock(db, "desk-mat") == 70


# ---- Medium 5: approvals can't happen twice; jobs can't run twice at once
def test_double_approve_creates_one_purchase_order(db):
    with db() as s:
        s.add(Recommendation(kind="reorder", target="desk-mat",
                             payload=json.dumps({"quantity": 5, "unit_cost": 600}), reason="r", impact=3000))
        s.commit()
    a, b = db(), db()
    a.get(Recommendation, 1), b.get(Recommendation, 1)
    automation.decide(a, 1, True, "o1")
    with pytest.raises(shop.ShopError, match="Already"):
        automation.decide(b, 1, True, "o2")
    a.close(); b.close()
    with db() as s:
        assert s.query(PurchaseOrder).count() == 1


def test_job_runs_once_at_a_time(db):
    with db() as s:
        s.add(JobLease(job="low_stock", holder="someone-else",
                       expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
        s.commit()
        run = automation.run_job(s, "low_stock")
    assert run.status == "skipped" and "already running" in run.message


def test_expired_lease_is_taken_over(db):
    with db() as s:
        s.add(JobLease(job="low_stock", holder="crashed", expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        s.commit()
        assert automation.run_job(s, "low_stock").status == "ok"
        assert s.query(JobLease).count() == 0  # released after the run


# ---- Medium 6: payments still in progress are not cancelled
def test_reconcile_leaves_in_progress_payments_alone(client, db, stripe_on, monkeypatch):
    o = pending_order(client)
    monkeypatch.setattr(payments, "retrieve_session", lambda sid: {"id": sid, "status": "complete", "payment_status": "unpaid"})
    with db() as s:
        assert payments.reconcile_pending(s, s.get(Order, o["id"])).startswith("waiting")
    assert status(db, o["id"]) == "pending_payment" and stock(db) == 18


# ---- Medium 7: orders with no saved Stripe session are recovered
def test_reconcile_recovers_order_without_session(client, db, stripe_on, monkeypatch):
    o = pending_order(client)
    with db() as s:
        s.get(Order, o["id"]).stripe_session_id = None  # server died before saving it
        s.commit()
    monkeypatch.setattr(payments, "retrieve_session", lambda sid: {"id": sid, "status": "open", "payment_status": "unpaid"})
    with db() as s:
        assert payments.reconcile_pending(s, s.get(Order, o["id"])) == "cancelled"
        assert s.get(Order, o["id"]).stripe_session_id == f"cs_{o['id']}"
    assert stock(db) == 20


# ---- Medium 8: staff can't accept payments or cancel
def test_staff_can_only_ship(client, db, stripe_on):
    o = pending_order(client)
    with db() as s:
        s.get(Order, o["id"]).status = "payment_review"
        s.commit()
        auth.create_user(s, "s@example.com", "staff password 123", "staff")
    t = client.post("/api/admin/login", json={"email": "s@example.com", "password": "staff password 123"}).json()["token"]
    h = {"X-Admin-Token": t}
    for new in ("paid", "cancelled"):
        r = client.post(f"/api/admin/orders/{o['id']}/status", json={"status": new}, headers=h)
        assert r.status_code == 403, new
    assert client.get("/api/admin/orders", headers=h).json()[0]["next_statuses"] == []
    assert status(db, o["id"]) == "payment_review"


# ---- Medium 9: production never gives orders away without payments
def test_production_without_stripe_refuses_checkout(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat"})
    r = client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER)
    assert r.status_code == 503
    assert client.get(f"/api/carts/{cid}").status_code == 200  # cart kept


# ---- Medium 10: deactivated products can't be bought
def test_inactive_product_in_cart_cannot_be_bought(client, db):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat"})
    with db() as s:
        s.get(Product, "desk-mat").active = False
        s.commit()
    assert client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER).status_code == 409
    assert stock(db, "desk-mat") == 50


# ---- Low 13: rate limits on anonymous writes and sign-in
def test_rate_limits(client):
    for i in range(10):
        assert client.post("/api/waitlist", json={"email": f"u{i}@example.com", "consent": True}).status_code == 201
    assert client.post("/api/waitlist", json={"email": "x@example.com", "consent": True}).status_code == 429
    for _ in range(20):
        client.post("/api/admin/login", json={"email": "a@example.com", "password": "wrong password"})
    assert client.post("/api/admin/login", json={"email": "a@example.com", "password": "wrong password"}).status_code == 429


# ---- Low 14: cancelling an unpaid order closes its Stripe checkout first
def test_admin_cancel_expires_stripe_session(client, db, stripe_on, monkeypatch):
    o = pending_order(client)
    expired = []
    monkeypatch.setattr(payments, "expire_session", lambda sid: expired.append(sid))
    with db() as s:
        admin.set_order_status(s, o["id"], "cancelled", actor="owner")
    assert expired == [f"cs_{o['id']}"] and stock(db) == 20


def test_admin_cancel_refused_if_stripe_cannot_close_checkout(client, db, stripe_on, monkeypatch):
    o = pending_order(client)
    def boom(sid):
        raise RuntimeError("session already complete")
    monkeypatch.setattr(payments, "expire_session", boom)
    with db() as s, pytest.raises(shop.ShopError, match="Stripe"):
        admin.set_order_status(s, o["id"], "cancelled", actor="owner")
    assert status(db, o["id"]) == "pending_payment" and stock(db) == 18


# ---- Low 15: order lookup without the email in the URL
def test_order_lookup_by_post(client):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat"})
    o = client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER).json()
    assert client.post(f"/api/orders/{o['id']}/lookup", json={"email": "JANE@example.com"}).status_code == 200
    assert client.post(f"/api/orders/{o['id']}/lookup", json={"email": "x@example.com"}).status_code == 404


# ---- Low 13/19: cleanup of old carts; automatic backups keep the newest N
def test_cleanup_removes_old_carts_and_their_items(client, db):
    old = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{old}/items", json={"product_id": "desk-mat"})
    new = client.post("/api/carts").json()["id"]
    with db() as s:
        s.get(Cart, old).created_at = datetime.now(timezone.utc) - timedelta(days=40)
        s.commit()
        assert automation.run_job(s, "cleanup").message == "removed 1 old cart(s)"
        assert s.get(Cart, new) is not None and s.query(CartItem).count() == 0


def test_automatic_backup_keeps_newest(db, tmp_path, monkeypatch):
    import sqlite3
    from app import backup
    f = tmp_path / "live.db"
    sqlite3.connect(f).executescript("CREATE TABLE products(id); CREATE TABLE orders(id); "
                                     "CREATE TABLE order_items(id); CREATE TABLE admin_audit(id);")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{f}")
    monkeypatch.setattr(settings, "backup_keep", 2)
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "b"))
    with db() as s:
        for _ in range(3):
            assert automation.run_job(s, "backup").status == "ok"
    assert len(backup.list_backups()) == 2
