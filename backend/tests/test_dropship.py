"""Dropshipping: sell without buying stock; each paid order becomes a supplier order."""
import pytest

from app.config import settings
from app.models import Order, Product, SupplierOrder
from app.services import admin, auth, automation, payments

CUSTOMER = {"name": "Jane Doe", "email": "jane@example.com", "address": "1 Main St, London"}


def make_dropship(db, pid="desk-mat", cost=900, stock=0):
    with db() as s:
        p = s.get(Product, pid)
        p.fulfilment, p.supplier_name, p.supplier_url = "dropship", "Acme Supply", "https://supplier.example/desk-mat"
        p.supplier_cost, p.delivery_estimate, p.stock = cost, "7-12 working days", stock
        s.commit()


@pytest.fixture()
def owner(client, db):
    with db() as s:
        auth.create_user(s, "o@example.com", "owner password 123", "owner")
        auth.create_user(s, "s@example.com", "staff password 123", "staff")
    t = client.post("/api/admin/login", json={"email": "o@example.com", "password": "owner password 123"}).json()["token"]
    return {"X-Admin-Token": t}


def buy(client, pid="desk-mat", qty=2):
    cid = client.post("/api/carts").json()["id"]
    r = client.post(f"/api/carts/{cid}/items", json={"product_id": pid, "quantity": qty})
    assert r.status_code == 200, r.text
    return client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER).json()


def test_dropship_product_sells_with_zero_stock(client, db):
    make_dropship(db, stock=0)
    p = client.get("/api/products/desk-mat").json()
    assert p["in_stock"] is True and p["delivery_estimate"] == "7-12 working days"
    assert "supplier_cost" not in p and "supplier_url" not in p  # never public
    order = buy(client)
    assert order["status"] == "placed"
    with db() as s:
        assert s.get(Product, "desk-mat").stock == 0  # nothing taken
        so = s.query(SupplierOrder).one()
        assert (so.quantity, so.supplier_cost_total, so.sale_total, so.status) == (2, 1800, 6400, "to_order")


def test_mixed_order_only_touches_own_stock(client, db):
    make_dropship(db, "desk-mat")
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat", "quantity": 1})
    client.post(f"/api/carts/{cid}/items", json={"product_id": "monitor-riser", "quantity": 2})
    client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER)
    with db() as s:
        assert s.get(Product, "monitor-riser").stock == 18
        assert [so.product_id for so in s.query(SupplierOrder)] == ["desk-mat"]


def test_cancelling_never_adds_phantom_dropship_stock(client, db, monkeypatch):
    make_dropship(db, "desk-mat")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(payments, "create_checkout_session", lambda o: (f"cs_{o.id}", "https://stripe.test"))
    monkeypatch.setattr(payments, "expire_session", lambda sid: None)
    order = buy(client)
    assert order["status"] == "pending_payment"
    with db() as s:
        admin.set_order_status(s, order["id"], "cancelled", actor="owner")
        assert s.get(Product, "desk-mat").stock == 0  # not 2
        assert s.query(SupplierOrder).count() == 0  # unpaid: nothing to buy


def test_supplier_order_created_only_when_paid_and_only_once(client, db, monkeypatch):
    make_dropship(db, "desk-mat")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(payments, "create_checkout_session", lambda o: (f"cs_{o.id}", "https://stripe.test"))
    order = buy(client)
    with db() as s:
        assert s.query(SupplierOrder).count() == 0
        ev = {"type": "checkout.session.completed", "data": {"object": {
            "id": f"cs_{order['id']}", "client_reference_id": order["id"], "payment_status": "paid",
            "amount_total": order["total"], "currency": "gbp"}}}
        payments.handle_event(s, {**ev, "id": "evt_a"})
        payments.handle_event(s, {**ev, "id": "evt_b"})  # a second delivery
        assert s.get(Order, order["id"]).status == "paid"
        assert s.query(SupplierOrder).count() == 1


def test_owner_sets_up_dropship_product_and_processes_supplier_order(client, db, owner):
    r = client.patch("/api/admin/products/cable-clips", headers=owner, json={
        "fulfilment": "dropship", "supplier_name": "Clip Co", "supplier_url": "https://clips.example/p/1",
        "supplier_cost": 500, "delivery_estimate": "5-8 working days", "note": "switch to dropship"})
    assert r.status_code == 200 and r.json()["fulfilment"] == "dropship"
    assert r.json()["contribution_pre_ads"] > 0  # economics use the supplier price
    buy(client, "cable-clips", 1)
    rows = client.get("/api/admin/supplier-orders", headers=owner).json()
    so = rows[0]
    assert so["ship_to_name"] == "Jane Doe" and so["ship_to_address"] == "1 Main St, London"
    assert so["supplier_url"] == "https://clips.example/p/1"
    # GBP 18 sale: 15.00 ex VAT - 5.00 supplier - 0.27 Stripe = 9.73
    assert so["profit_estimate"] == 973
    assert so["next_statuses"] == ["ordered", "problem"]
    r = client.post(f"/api/admin/supplier-orders/{so['id']}", headers=owner,
                    json={"status": "ordered", "supplier_ref": "SUP-123"})
    assert r.json()["status"] == "ordered" and r.json()["supplier_ref"] == "SUP-123"
    r = client.post(f"/api/admin/supplier-orders/{so['id']}", headers=owner,
                    json={"status": "shipped", "tracking": "RM123GB"})
    assert r.json()["tracking"] == "RM123GB"
    assert client.post(f"/api/admin/supplier-orders/{so['id']}", headers=owner,
                       json={"status": "to_order"}).status_code == 409


def test_supplier_link_must_be_a_web_link(client, owner):
    r = client.patch("/api/admin/products/desk-mat", headers=owner,
                     json={"supplier_url": "javascript:alert(1)"})
    assert r.status_code == 422
    assert client.patch("/api/admin/products/desk-mat", headers=owner,
                        json={"fulfilment": "magic"}).status_code == 422


def test_staff_cannot_see_supplier_orders(client, db, owner):
    t = client.post("/api/admin/login", json={"email": "s@example.com", "password": "staff password 123"}).json()["token"]
    assert client.get("/api/admin/supplier-orders", headers={"X-Admin-Token": t}).status_code == 403


def test_no_reorders_for_dropship_and_margin_uses_supplier_price(db):
    make_dropship(db, "desk-mat", cost=2500)  # GBP 25 supplier price on a GBP 32 sale: thin margin
    with db() as s:
        low = automation.run_job(s, "low_stock")
        assert "desk-mat" not in low.message
        guard = automation.run_job(s, "margin_guard")
        assert "desk-mat" in guard.message  # margin too low -> price suggestion


def test_daily_report_lists_supplier_orders_to_place(client, db):
    make_dropship(db)
    buy(client)
    from datetime import datetime, timezone
    with db() as s:
        text = automation.build_report(s, datetime.now(timezone.utc))
    assert "Supplier orders to place (dropship): 1" in text
