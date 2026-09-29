import hashlib
import hmac
import json
import time

import pytest

from app.config import settings
from app.models import Order, Product
from app.services import payments

CUSTOMER = {"name": "Jane Doe", "email": "jane@example.com", "address": "1 Main St, London"}
WHSEC = "whsec_test_secret"


class FakeSession:
    id = "cs_test_123"
    url = "https://checkout.stripe.com/c/pay/cs_test_123"


@pytest.fixture()
def stripe_on(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", WHSEC)
    calls = []

    def fake_create(order):
        calls.append(order)
        return FakeSession.id, FakeSession.url

    monkeypatch.setattr(payments, "create_checkout_session", fake_create)
    return calls


def place_order(client, product_id="desk-mat", qty=1):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": product_id, "quantity": qty})
    return client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER)


def send_event(client, event, secret=WHSEC, signature=None):
    payload = json.dumps(event)
    if signature is None:
        ts = int(time.time())
        sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
        signature = f"t={ts},v1={sig}"
    return client.post("/api/webhooks/stripe", content=payload,
                       headers={"stripe-signature": signature, "content-type": "application/json"})


def session_event(order_id, type_="checkout.session.completed", event_id="evt_1", **session):
    obj = {"id": FakeSession.id, "client_reference_id": order_id, "payment_status": "paid",
           "currency": "gbp", **session}
    return {"id": event_id, "type": type_, "data": {"object": obj}}


def order_status(db, order_id):
    with db() as s:
        return s.get(Order, order_id).status


def stock(db, product_id):
    with db() as s:
        return s.get(Product, product_id).stock


def test_checkout_returns_stripe_url_and_reserves_stock(client, db, stripe_on):
    r = place_order(client)
    assert r.status_code == 201
    assert r.json()["checkout_url"] == FakeSession.url
    assert r.json()["status"] == "pending_payment"
    assert stock(db, "desk-mat") == 49
    with db() as s:
        assert s.get(Order, r.json()["id"]).stripe_session_id == FakeSession.id


def test_paid_webhook_marks_order_paid(client, db, stripe_on):
    order = place_order(client).json()
    r = send_event(client, session_event(order["id"], amount_total=order["total"]))
    assert r.status_code == 200 and r.json()["outcome"] == "paid"
    assert order_status(db, order["id"]) == "paid"


def test_duplicate_event_is_applied_once(client, db, stripe_on):
    order = place_order(client).json()
    expired = session_event(order["id"], "checkout.session.expired", "evt_dup")
    assert send_event(client, expired).json()["outcome"] == "cancelled"
    assert send_event(client, expired).json()["outcome"] == "duplicate"
    assert stock(db, "desk-mat") == 50  # released exactly once


def test_amount_mismatch_goes_to_review(client, db, stripe_on):
    order = place_order(client).json()
    send_event(client, session_event(order["id"], amount_total=order["total"] - 1))
    assert order_status(db, order["id"]) == "payment_review"


def test_wrong_currency_goes_to_review(client, db, stripe_on):
    order = place_order(client).json()
    send_event(client, session_event(order["id"], amount_total=order["total"], currency="usd"))
    assert order_status(db, order["id"]) == "payment_review"


def test_unpaid_completion_stays_pending_then_async_success(client, db, stripe_on):
    order = place_order(client).json()
    send_event(client, session_event(order["id"], payment_status="unpaid", amount_total=order["total"]))
    assert order_status(db, order["id"]) == "pending_payment"
    send_event(client, session_event(order["id"], "checkout.session.async_payment_succeeded", "evt_2",
                                     amount_total=order["total"]))
    assert order_status(db, order["id"]) == "paid"


def test_expired_session_cancels_and_releases_stock(client, db, stripe_on):
    order = place_order(client, "monitor-riser", 3).json()
    assert stock(db, "monitor-riser") == 17
    send_event(client, session_event(order["id"], "checkout.session.expired"))
    assert order_status(db, order["id"]) == "cancelled"
    assert stock(db, "monitor-riser") == 20


def test_late_expiry_never_cancels_paid_order(client, db, stripe_on):
    order = place_order(client).json()
    send_event(client, session_event(order["id"], amount_total=order["total"]))
    send_event(client, session_event(order["id"], "checkout.session.expired", "evt_late"))
    assert order_status(db, order["id"]) == "paid"
    assert stock(db, "desk-mat") == 49


def test_bad_signature_rejected(client, db, stripe_on):
    order = place_order(client).json()
    event = session_event(order["id"], amount_total=order["total"])
    assert send_event(client, event, secret="whsec_wrong").status_code == 400
    assert send_event(client, event, signature="garbage").status_code == 400
    assert order_status(db, order["id"]) == "pending_payment"


def test_webhook_fails_closed_without_secret(client):
    assert send_event(client, {"id": "evt_x", "type": "x"}).status_code == 503


def test_unknown_events_are_acknowledged(client, stripe_on):
    r = send_event(client, {"id": "evt_other", "type": "customer.created", "data": {"object": {}}})
    assert r.status_code == 200 and r.json()["outcome"] == "ignored"


def test_stripe_outage_cancels_order_and_releases_stock(client, db, stripe_on, monkeypatch):
    def boom(order):
        raise RuntimeError("stripe down")

    monkeypatch.setattr(payments, "create_checkout_session", boom)
    r = place_order(client, "cable-tray", 2)
    assert r.status_code == 502
    assert stock(db, "cable-tray") == 50
    with db() as s:
        assert [o.status for o in s.query(Order).all()] == ["cancelled"]


def test_session_params_are_correct(monkeypatch):
    """The real Stripe call is built with pence amounts, GBP and shipping."""
    captured = {}

    class FakeSessions:
        def create(self, params, options=None):
            captured.update(params=params, options=options)
            return FakeSession()

    class FakeClient:
        class v1:
            class checkout:
                sessions = FakeSessions()

    monkeypatch.setattr(payments, "_stripe_client", lambda: FakeClient())
    from app.models import OrderItem
    order = Order(id="ord-1", customer_name="J", customer_email="j@example.com", shipping_address="x",
                  subtotal=3200, shipping=395, total=3595,
                  items=[OrderItem(product_id="desk-mat", name="Desk Mat", unit_price=3200, quantity=1)])
    assert payments.create_checkout_session(order) == (FakeSession.id, FakeSession.url)
    p = captured["params"]
    assert p["client_reference_id"] == "ord-1"
    assert p["line_items"][0]["price_data"] == {"currency": "gbp", "unit_amount": 3200,
                                                "product_data": {"name": "Desk Mat"}}
    assert p["shipping_options"][0]["shipping_rate_data"]["fixed_amount"] == {"amount": 395, "currency": "gbp"}
    assert captured["options"] == {"idempotency_key": "checkout-ord-1"}
    assert p["expires_at"] >= time.time() + 29 * 60
