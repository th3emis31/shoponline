"""Email flows and consent (Blueprint section I; UK PECR / GDPR)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models import EmailMessage, MarketingConsent, Order
from app.services import admin, auth, emails, payments

CUSTOMER = {"name": "Jane Doe", "email": "jane@example.com", "address": "1 Main St, London"}


def msgs(db, **f):
    with db() as s:
        return s.query(EmailMessage).filter_by(**f).order_by(EmailMessage.id).all()


def buy(client, consent=False, pid="desk-mat", email=None):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": pid})
    body = {**CUSTOMER, "marketing_consent": consent, **({"email": email} if email else {})}
    return client.post(f"/api/carts/{cid}/checkout", json=body).json()


def run_sender(db, when=None):
    """Send everything due by `when` (default: far future)."""
    with db() as s:
        for m in s.query(EmailMessage).filter_by(status="queued"):
            if when is None:
                m.send_after = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.commit()
        return emails.send_due(s, limit=500)


def test_order_without_consent_gets_only_service_emails(client, db):
    buy(client)
    flows = [(m.flow, m.step, m.kind) for m in msgs(db)]
    assert flows == [("order", 1, "transactional"), ("post_purchase", 3, "transactional")]
    run_sender(db)
    sent = msgs(db, status="outbox")
    assert len(sent) == 2 and "Thanks for your order" in sent[0].body and "Total (inc. VAT): £35.95" in sent[0].body
    assert "Unsubscribe" not in sent[0].body  # not marketing


def test_order_with_consent_adds_review_and_followup(client, db):
    buy(client, consent=True)
    assert [(m.flow, m.step) for m in msgs(db)] == [("order", 1), ("post_purchase", 3), ("post_purchase", 4), ("post_purchase", 5)]
    run_sender(db)
    review = msgs(db, flow="post_purchase", step=4)[0]
    assert "/review/" in review.body and "Unsubscribe with one click" in review.body


def test_waitlist_is_launch_only(client, db):
    client.post("/api/waitlist", json={"email": "w@example.com", "consent": True})
    with db() as s:
        c = s.get(MarketingConsent, "w@example.com")
        assert c.scope == "launch_only"
        assert not emails.may_market(s, "w@example.com", "welcome")
        assert emails.may_market(s, "w@example.com", "launch")
    assert msgs(db) == []  # nothing sent on sign-up


def test_launch_email_once_per_person(client, db):
    client.post("/api/waitlist", json={"email": "w@example.com", "consent": True})
    client.post("/api/newsletter", json={"email": "n@example.com", "consent": True})
    with db() as s:
        auth.create_user(s, "o@example.com", "owner password 123", "owner")
    t = {"X-Admin-Token": client.post("/api/admin/login", json={"email": "o@example.com", "password": "owner password 123"}).json()["token"]}
    assert client.post("/api/admin/emails/launch", headers=t).json()["queued"] == 2
    assert client.post("/api/admin/emails/launch", headers=t).json()["queued"] == 0  # never twice
    assert len(msgs(db, flow="launch")) == 2


def test_newsletter_welcome_series_and_unsubscribe(client, db):
    assert client.post("/api/newsletter", json={"email": "n@example.com", "consent": False}).status_code == 400
    assert client.post("/api/newsletter", json={"email": "N@example.com", "consent": True}).status_code == 201
    welcome = msgs(db, flow="welcome")
    assert [m.step for m in welcome] == [1, 2, 3, 4, 5]
    assert welcome[4].send_after - welcome[0].send_after >= timedelta(days=9)
    # send only the first (the others are in the future)
    with db() as s:
        print(emails.send_due(s))
    first = msgs(db, flow="welcome", step=1)[0]
    assert first.status == "outbox" and "token=" in first.body
    token = first.body.split("token=")[1].split()[0]
    r = client.post("/api/email/unsubscribe", json={"token": token})
    assert r.status_code == 200
    assert {m.status for m in msgs(db, flow="welcome") if m.step > 1} == {"cancelled"}
    assert client.post("/api/email/unsubscribe", json={"token": "x" * 20}).status_code == 404


def test_abandoned_checkout_emails_need_consent_and_stop_after_purchase(client, db, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(payments, "create_checkout_session", lambda o: (f"cs_{o.id}", "https://stripe.test"))
    no_consent = buy(client, consent=False, email="quiet@example.com")
    with_consent = buy(client, consent=True)
    again = buy(client, consent=True)  # same person abandons a second time
    with db() as s:
        for o in (no_consent, with_consent, again):
            payments.handle_event(s, {"id": f"e_{o['id']}", "type": "checkout.session.expired",
                                      "data": {"object": {"id": f"cs_{o['id']}", "client_reference_id": o["id"]}}})
    ab = msgs(db, flow="abandoned")
    # no email for the person without consent; ONE series (not two) for the other
    assert len(ab) == 4 and all(m.dedupe_key.endswith(with_consent["id"]) for m in ab)
    # the customer comes back and buys: remaining reminders are skipped
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    buy(client, consent=True)
    run_sender(db)
    assert {m.status for m in msgs(db, flow="abandoned")} == {"skipped"}


def test_shipped_email_includes_tracking(client, db):
    o = buy(client)
    with db() as s:
        admin.set_order_status(s, o["id"], "shipped", note="RM123456GB", actor="owner")
    shipped = msgs(db, flow="order", step=2)[0]
    assert "RM123456GB" in shipped.body


def test_winback_after_90_days_only_with_consent(client, db):
    buy(client, consent=True)
    with db() as s:
        for o in s.query(Order):
            o.created_at = datetime.now(timezone.utc) - timedelta(days=95)
        s.commit()
        assert emails.queue_winbacks(s) == 1
        assert emails.queue_winbacks(s) == 0  # once


def test_smtp_mode_sends_and_retries(client, db, monkeypatch):
    monkeypatch.setattr(settings, "email_mode", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example")
    sent = []
    monkeypatch.setattr(emails, "_smtp_send", lambda m: sent.append(m.to_email))
    buy(client)
    run_sender(db)
    assert sent == ["jane@example.com", "jane@example.com"]
    assert {m.status for m in msgs(db)} == {"sent"}


def test_smtp_failures_are_retried_then_marked_failed(client, db, monkeypatch):
    monkeypatch.setattr(settings, "email_mode", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example")
    def boom(m):
        raise OSError("connection refused")
    monkeypatch.setattr(emails, "_smtp_send", boom)
    buy(client)
    for _ in range(5):
        run_sender(db)
    assert {m.status for m in msgs(db)} == {"failed"}


def test_signed_links(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "k1")
    t = emails.sign("review:abc")
    assert emails.verify("review:abc", t) and not emails.verify("review:abd", t)
    monkeypatch.setattr(settings, "secret_key", "k2")
    assert not emails.verify("review:abc", t)


def test_link_key_never_uses_public_default_in_production(monkeypatch):
    from app.config import settings
    from app.services import emails as em

    monkeypatch.setattr(settings, "secret_key", "")
    monkeypatch.setattr(settings, "environment", "development")
    dev = em.sign("x")
    monkeypatch.setattr(settings, "environment", "production")
    prod = em.sign("x")
    assert prod != dev  # production never signs with the known dev key
    monkeypatch.setattr(settings, "secret_key", "a-long-random-secret")
    assert em.sign("x") not in (dev, prod)
    assert em.verify("x", em.sign("x"))
