"""Support inbox: contact form, templates, 1-business-day target (Blueprint section O)."""
from datetime import datetime, timedelta, timezone

from app.models import EmailMessage, SupportTicket
from app.services import support

MSG = {"name": "Sam Smith", "email": "Sam@Example.com", "topic": "order", "message": "Where is my parcel please?"}


def owner(client, db, role="owner", email="owner@example.com"):
    from app.services import auth
    with db() as s:
        auth.create_user(s, email, "a long owner password", role)
        s.commit()
    t = client.post("/api/admin/login", json={"email": email, "password": "a long owner password"}).json()["token"]
    return {"x-admin-token": t}


def test_due_is_one_business_day():
    fri = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)  # Friday
    assert support.due_after(fri).weekday() == 0  # Monday
    tue = datetime(2026, 9, 29, 10, tzinfo=timezone.utc)
    assert support.due_after(tue) == tue + timedelta(days=1)
    sat = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    assert support.due_after(sat).weekday() == 0


def test_contact_form_creates_ticket_and_acknowledges(client, db):
    r = client.post("/api/contact", json=MSG)
    assert r.status_code == 201 and "1 business day" in r.json()["message"]
    with db() as s:
        t = s.query(SupportTicket).one()
        assert t.email == "sam@example.com" and t.status == "open"
        ack = s.query(EmailMessage).filter_by(flow="support", step=1).one()
        assert ack.kind == "transactional" and "Where is my parcel" in ack.body


def test_honeypot_drops_bots(client, db):
    assert client.post("/api/contact", json={**MSG, "website": "http://spam"}).status_code == 201
    with db() as s:
        assert s.query(SupportTicket).count() == 0


def test_contact_validation(client):
    assert client.post("/api/contact", json={**MSG, "topic": "hack"}).status_code == 422
    assert client.post("/api/contact", json={**MSG, "email": "nope"}).status_code == 422
    assert client.post("/api/contact", json={**MSG, "message": "hi"}).status_code == 422


def test_staff_reply_with_template_emails_customer(client, db):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat"})
    order = client.post(f"/api/carts/{cid}/checkout", json={"name": "Sam Smith", "email": "sam@example.com",
                                                             "address": "1 Road"}).json()
    client.post("/api/contact", json={**MSG, "order_id": order["id"]})
    h = owner(client, db, role="staff", email="staff@example.com")
    inbox = client.get("/api/admin/support", headers=h).json()
    tid = inbox["tickets"][0]["id"]
    assert inbox["open"] == 1 and "where_is_order" in inbox["templates"]
    text = client.get(f"/api/admin/support/{tid}/template/where_is_order", headers=h).json()["text"]
    assert "Hi Sam" in text and order["id"][:8] in text and "placed" in text
    r = client.post(f"/api/admin/support/{tid}/reply", headers=h, json={"body": text})
    assert r.status_code == 201
    with db() as s:
        t = s.get(SupportTicket, tid)
        assert t.status == "replied" and t.first_reply_at is not None
        sent = s.query(EmailMessage).filter_by(flow="support", step=2).one()
        assert sent.to_email == "sam@example.com" and "Hi Sam" in sent.body
    inbox = client.get("/api/admin/support", headers=h).json()
    assert inbox["on_time_rate"] == 1.0 and inbox["tickets"][0]["replies"][0]["by"] == "staff@example.com"


def test_template_never_leaks_someone_elses_order(client, db):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat"})
    other = client.post(f"/api/carts/{cid}/checkout", json={"name": "Other", "email": "other@example.com",
                                                             "address": "2 Road"}).json()
    client.post("/api/contact", json={**MSG, "order_id": other["id"]})
    h = owner(client, db)
    tid = client.get("/api/admin/support", headers=h).json()["tickets"][0]["id"]
    text = client.get(f"/api/admin/support/{tid}/template/where_is_order", headers=h).json()["text"]
    assert other["id"][:8] not in text and "(order number)" in text


def test_overdue_is_flagged_and_in_daily_report(client, db):
    client.post("/api/contact", json=MSG)
    with db() as s:
        t = s.query(SupportTicket).one()
        t.due_at = datetime.now(timezone.utc) - timedelta(hours=1)
        s.commit()
        assert support.overdue_count(s) == 1
        from app.services import automation
        assert "past the 1-business-day target: 1" in automation.build_report(s, datetime.now(timezone.utc))
    h = owner(client, db)
    inbox = client.get("/api/admin/support", headers=h).json()
    assert inbox["overdue"] == 1 and inbox["tickets"][0]["overdue"] is True


def test_empty_reply_and_unknown_ticket(client, db):
    h = owner(client, db)
    assert client.post("/api/admin/support/999/reply", headers=h, json={"body": "hi"}).status_code == 404
    client.post("/api/contact", json=MSG)
    tid = client.get("/api/admin/support", headers=h).json()["tickets"][0]["id"]
    assert client.post(f"/api/admin/support/{tid}/reply", headers=h, json={"body": "   "}).status_code == 400
    assert client.post(f"/api/admin/support/{tid}/status", headers=h, json={"status": "closed"}).json()["status"] == "closed"
    assert client.get("/api/admin/support").status_code in (401, 503)
