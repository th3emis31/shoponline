import json
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models import (AdminAudit, AutomationRun, DailyReport, Order, Product, PurchaseOrder,
                        Recommendation)
from app.services import auth, automation, payments

CUSTOMER = {"name": "Jane", "email": "jane@example.com", "address": "1 Main St"}


def set_product(db, pid, **fields):
    with db() as s:
        p = s.get(Product, pid)
        for k, v in fields.items():
            setattr(p, k, v)
        s.commit()


def get(db, model, key):
    with db() as s:
        return s.get(model, key)


def run(db, job):
    with db() as s:
        return automation.run_job(s, job)


def recs(db, **filters):
    with db() as s:
        return s.query(Recommendation).filter_by(**filters).all()


@pytest.fixture()
def owner(client, db):
    with db() as s:
        auth.create_user(s, "owner@example.com", "owner password 123", "owner")
        auth.create_user(s, "staff@example.com", "staff password 123", "staff")
    t = client.post("/api/admin/login", json={"email": "owner@example.com", "password": "owner password 123"}).json()["token"]
    return {"X-Admin-Token": t}


# ---------- low stock / reorders

def test_small_reorder_runs_automatically(db):
    set_product(db, "cable-clips", stock=5)  # 20 x GBP 3 = GBP 60, under the GBP 100 limit
    r = run(db, "low_stock")
    assert r.status == "ok" and "cable-clips (executed)" in r.message
    with db() as s:
        po = s.query(PurchaseOrder).one()
        assert (po.product_id, po.quantity, po.total, po.status) == ("cable-clips", 20, 6000, "approved")
        rec = s.query(Recommendation).one()
        assert rec.auto and rec.decided_by == "automation" and "within limits" in rec.decision_note
        assert s.query(AdminAudit).filter_by(action="purchase_order.create", actor="automation").count() == 1


def test_big_reorder_waits_for_approval(db):
    set_product(db, "desk-mat", stock=3)  # 20 x GBP 6 = GBP 120 > GBP 100
    run(db, "low_stock")
    (rec,) = recs(db, target="desk-mat")
    assert rec.status == "pending" and not rec.auto and "above the automatic limit" in rec.decision_note
    with db() as s:
        assert s.query(PurchaseOrder).count() == 0


def test_no_duplicate_reorders(db):
    set_product(db, "cable-clips", stock=5)
    set_product(db, "desk-mat", stock=3)
    run(db, "low_stock")
    run(db, "low_stock")  # open PO for clips, pending rec for mat: nothing new
    assert len(recs(db)) == 2


def test_weekly_limit_stops_automatic_reorders(db, monkeypatch):
    monkeypatch.setattr(settings, "auto_reorder_weekly_max", 10000)
    set_product(db, "cable-clips", stock=0)       # GBP 60 -> auto
    set_product(db, "cable-tray", stock=0, reorder_qty=5)  # 5 x GBP 8 = GBP 40 -> would be GBP 100 total... equal is ok
    set_product(db, "monitor-riser", stock=0, reorder_qty=1)  # GBP 16 -> over GBP 100/week
    run(db, "low_stock")
    by = {r.target: r for r in recs(db)}
    assert by["cable-clips"].status == "executed"
    assert by["cable-tray"].status == "executed"
    assert by["monitor-riser"].status == "pending" and "weekly limit" in by["monitor-riser"].decision_note


def test_unknown_cost_needs_a_person(db):
    set_product(db, "cable-clips", stock=0, landed_cost=0)
    run(db, "low_stock")
    (rec,) = recs(db, target="cable-clips")
    assert rec.status == "pending" and "cost unknown" in rec.decision_note


# ---------- approvals

def test_owner_approves_and_rejects(client, db, owner):
    set_product(db, "desk-mat", stock=3)
    set_product(db, "monitor-riser", stock=3)
    run(db, "low_stock")
    pending = client.get("/api/admin/recommendations", params={"status": "pending"}, headers=owner).json()
    by = {r["target"]: r for r in pending}
    r = client.post(f"/api/admin/recommendations/{by['desk-mat']['id']}/approve", json={"note": "ok"}, headers=owner)
    assert r.status_code == 200 and r.json()["status"] == "executed" and "Purchase order" in r.json()["result"]
    r = client.post(f"/api/admin/recommendations/{by['monitor-riser']['id']}/reject", json={}, headers=owner)
    assert r.json()["status"] == "rejected"
    # can't decide twice
    assert client.post(f"/api/admin/recommendations/{by['desk-mat']['id']}/approve", json={}, headers=owner).status_code == 409
    with db() as s:
        assert s.query(AdminAudit).filter_by(action="recommendation.approve", actor="owner@example.com").count() == 1


def test_staff_cannot_use_automation(client, db, owner):
    t = client.post("/api/admin/login", json={"email": "staff@example.com", "password": "staff password 123"}).json()["token"]
    h = {"X-Admin-Token": t}
    for path in ("/api/admin/automation", "/api/admin/recommendations", "/api/admin/purchase-orders",
                 "/api/admin/reports/latest"):
        assert client.get(path, headers=h).status_code == 403, path
    assert client.post("/api/admin/automation/run/low_stock", headers=h).status_code == 403
    assert client.post("/api/admin/recommendations/1/approve", json={}, headers=h).status_code == 403


# ---------- purchase orders

def test_receiving_a_purchase_order_adds_stock(client, db, owner):
    set_product(db, "cable-clips", stock=5)
    run(db, "low_stock")
    po = client.get("/api/admin/purchase-orders", headers=owner).json()[0]
    assert po["next_statuses"] == ["cancelled", "sent"]
    assert client.post(f"/api/admin/purchase-orders/{po['id']}/status", json={"status": "received"}, headers=owner).status_code == 409
    client.post(f"/api/admin/purchase-orders/{po['id']}/status", json={"status": "sent"}, headers=owner)
    r = client.post(f"/api/admin/purchase-orders/{po['id']}/status", json={"status": "received"}, headers=owner)
    assert r.json()["status"] == "received"
    assert get(db, Product, "cable-clips").stock == 25
    # received is final: stock can't be added twice
    assert client.post(f"/api/admin/purchase-orders/{po['id']}/status", json={"status": "received"}, headers=owner).status_code == 409


# ---------- margin guard / prices

def test_small_price_rise_to_protect_margin_is_automatic(db):
    set_product(db, "desk-mat", landed_cost=1111)  # margin ~34.5% < 35%
    r = run(db, "margin_guard")
    assert "desk-mat (executed)" in r.message
    price = get(db, Product, "desk-mat").price
    assert 3200 < price <= 3200 * 1.05 and price % 50 == 0
    from app.services import unit_economics as ue
    p = get(db, Product, "desk-mat")
    assert ue.calculate(p.price, p.landed_cost, p.shipping_cost, p.packaging_cost).contribution_margin >= 0.35


def test_big_price_rise_waits_for_approval(db):
    set_product(db, "desk-mat", landed_cost=1500)  # needs a large rise
    run(db, "margin_guard")
    (rec,) = recs(db, target="desk-mat")
    assert rec.status == "pending" and "above the automatic limit" in rec.decision_note
    assert get(db, Product, "desk-mat").price == 3200  # unchanged until approved


def test_stale_price_suggestion_is_not_applied(client, db, owner):
    set_product(db, "desk-mat", landed_cost=1500)
    run(db, "margin_guard")
    (rec,) = recs(db, target="desk-mat")
    set_product(db, "desk-mat", price=4500)  # someone changed it meanwhile
    r = client.post(f"/api/admin/recommendations/{rec.id}/approve", json={}, headers=owner)
    assert r.status_code == 409 and "Price changed" in r.json()["error"]
    assert get(db, Product, "desk-mat").price == 4500
    assert recs(db, target="desk-mat")[0].status == "pending"


def test_automation_never_lowers_prices(db):
    with db() as s:
        rec = Recommendation(kind="price_change", target="desk-mat",
                             payload=json.dumps({"old_price": 3200, "new_price": 3100}), reason="x", impact=-100)
        s.add(rec)
        s.flush()
        ok, why = automation.auto_decision(s, rec)
    assert not ok and "never lowers" in why


def test_healthy_margins_change_nothing(db):
    r = run(db, "margin_guard")
    assert r.message == "all margins at or above minimum" and recs(db) == []


# ---------- abandoned checkouts

@pytest.fixture()
def stripe_order(client, db, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(payments, "create_checkout_session", lambda order: ("cs_old", "https://stripe.test"))
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "monitor-riser", "quantity": 2})
    order = client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER).json()
    with db() as s:  # make it old
        o = s.get(Order, order["id"])
        o.created_at = datetime.now(timezone.utc) - timedelta(hours=3)
        s.commit()
    return order


def test_abandoned_open_checkout_is_expired_and_stock_released(db, stripe_order, monkeypatch):
    expired = []
    monkeypatch.setattr(payments, "retrieve_session", lambda sid: {"id": sid, "status": "open", "payment_status": "unpaid"})
    monkeypatch.setattr(payments, "expire_session", lambda sid: expired.append(sid))
    assert get(db, Product, "monitor-riser").stock == 18
    r = run(db, "close_abandoned_checkouts")
    assert r.status == "ok" and "cancelled" in r.message
    assert expired == ["cs_old"]
    assert get(db, Order, stripe_order["id"]).status == "cancelled"
    assert get(db, Product, "monitor-riser").stock == 20


def test_missed_payment_webhook_is_recovered_as_paid(db, stripe_order, monkeypatch):
    monkeypatch.setattr(payments, "retrieve_session", lambda sid: {
        "id": sid, "status": "complete", "payment_status": "paid",
        "amount_total": stripe_order["total"], "currency": "gbp"})
    run(db, "close_abandoned_checkouts")
    assert get(db, Order, stripe_order["id"]).status == "paid"
    assert get(db, Product, "monitor-riser").stock == 18  # sold, not released


def test_stripe_outage_leaves_orders_untouched(db, stripe_order, monkeypatch):
    def boom(sid):
        raise RuntimeError("stripe down")
    monkeypatch.setattr(payments, "retrieve_session", boom)
    r = run(db, "close_abandoned_checkouts")
    assert "error" in r.message
    assert get(db, Order, stripe_order["id"]).status == "pending_payment"
    assert get(db, Product, "monitor-riser").stock == 18


def test_recent_checkouts_are_left_alone(client, db, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(payments, "create_checkout_session", lambda order: ("cs_new", "https://stripe.test"))
    monkeypatch.setattr(payments, "retrieve_session", lambda sid: pytest.fail("must not call Stripe"))
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat"})
    client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER)
    assert "checked 0" in run(db, "close_abandoned_checkouts").message


def test_checkout_job_skipped_when_payments_off(db):
    r = run(db, "close_abandoned_checkouts")
    assert r.status == "skipped"


# ---------- scheduling, reports, backups, CLI

def test_schedule(db):
    now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    with db() as s:
        assert automation.is_due(s, "low_stock", now)
        s.add(AutomationRun(job="low_stock", started_at=now - timedelta(minutes=30), status="ok"))
        s.add(AutomationRun(job="backup", started_at=now - timedelta(hours=3), status="ok"))  # today, 09:00
        s.commit()
        assert not automation.is_due(s, "low_stock", now)
        assert automation.is_due(s, "low_stock", now + timedelta(minutes=31))
        assert not automation.is_due(s, "backup", now)  # already ran today
        assert automation.is_due(s, "backup", now + timedelta(days=1))
        early = datetime(2026, 9, 30, 1, 0, tzinfo=timezone.utc)
        assert not automation.is_due(s, "backup", early)  # before 02:00


def test_a_failing_job_is_recorded_not_raised(db, monkeypatch):
    def boom(s):
        raise RuntimeError("disk full")
    monkeypatch.setitem(automation.JOBS, "low_stock", (boom, "every", 60))
    r = run(db, "low_stock")
    assert r.status == "error" and "disk full" in r.message


def test_daily_report(client, db):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat", "quantity": 2})
    client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER)
    with db() as s:
        text = automation.build_report(s, datetime.now(timezone.utc))
    assert "Orders: 1" in text and "GBP 64.00" in text and "Orders to ship: 1" in text
    assert "Contribution before ads (ESTIMATE): GBP 28.88" in text
    assert run(db, "daily_report").message.endswith("written")
    assert run(db, "daily_report").message.endswith("already exists")
    with db() as s:
        assert s.query(DailyReport).count() == 1


def test_backup_job(db, tmp_path, monkeypatch):
    import sqlite3
    dbfile = tmp_path / "live.db"
    sqlite3.connect(dbfile).executescript(
        "CREATE TABLE products(id); CREATE TABLE orders(id); CREATE TABLE order_items(id); CREATE TABLE admin_audit(id);")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{dbfile}")
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "b"))
    r = run(db, "backup")
    assert r.status == "ok" and "verified" in r.message


def test_admin_run_now_and_status(client, db, owner):
    set_product(db, "cable-clips", stock=1)
    r = client.post("/api/admin/automation/run/low_stock", headers=owner).json()
    assert r["status"] == "ok"
    assert client.post("/api/admin/automation/run/nope", headers=owner).status_code == 404
    st = client.get("/api/admin/automation", headers=owner).json()
    assert st["limits"]["auto_reorder_max"] == 10000
    low = next(j for j in st["jobs"] if j["job"] == "low_stock")
    assert low["last_status"] == "ok" and low["schedule"] == "every 60 min"


def test_cli(db, monkeypatch, capsys):
    import app.automation_cli as cli
    monkeypatch.setattr(cli, "SessionLocal", db)
    monkeypatch.setattr(cli, "inspect", lambda _e: type("I", (), {"has_table": lambda self, n: True})())
    set_product(db, "cable-clips", stock=0)
    assert cli.main(["run", "low_stock"]) == 0
    assert "low_stock: ok" in capsys.readouterr().out
    cli.main(["status"])
    out = capsys.readouterr().out
    assert "Limits: reorders up to GBP 100.00" in out and "low_stock" in out
    cli.main(["report"])
    assert "No report yet" in capsys.readouterr().out
