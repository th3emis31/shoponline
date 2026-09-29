from app.models import WaitlistSignup
from app.services import auth


def test_join_requires_consent_and_valid_email(client):
    assert client.post("/api/waitlist", json={"email": "a@example.com", "consent": False}).status_code == 400
    assert client.post("/api/waitlist", json={"email": "not-an-email", "consent": True}).status_code == 422
    assert client.post("/api/waitlist", json={"email": "a@example.com"}).status_code == 422  # consent missing


def test_join_is_idempotent_and_does_not_reveal_duplicates(client, db):
    first = client.post("/api/waitlist", json={"email": "A@Example.com ", "consent": True, "product_id": "desk-mat"})
    again = client.post("/api/waitlist", json={"email": "a@example.com", "consent": True, "product_id": "desk-mat"})
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    client.post("/api/waitlist", json={"email": "a@example.com", "consent": True})  # whole-shop list
    client.post("/api/waitlist", json={"email": "a@example.com", "consent": True})
    with db() as s:
        rows = s.query(WaitlistSignup).all()
        assert len(rows) == 2
        assert all(r.email == "a@example.com" and "unsubscribe" in r.consent_text for r in rows)


def test_unknown_product_is_recorded_as_whole_shop(client, db):
    client.post("/api/waitlist", json={"email": "b@example.com", "consent": True, "product_id": "nope"})
    with db() as s:
        assert s.query(WaitlistSignup).one().product_id is None


def test_owner_sees_counts_staff_does_not(client, db):
    with db() as s:
        auth.create_user(s, "o@example.com", "owner password 123", "owner")
        auth.create_user(s, "s@example.com", "staff password 123", "staff")
    for e in ("x@example.com", "y@example.com"):
        client.post("/api/waitlist", json={"email": e, "consent": True, "product_id": "desk-mat"})
    client.post("/api/waitlist", json={"email": "z@example.com", "consent": True})

    def token(email, pw):
        return {"X-Admin-Token": client.post("/api/admin/login", json={"email": email, "password": pw}).json()["token"]}

    r = client.get("/api/admin/waitlist", headers=token("o@example.com", "owner password 123")).json()
    assert r["total"] == 3
    assert r["by_product"][0] == {"product_id": "desk-mat", "count": 2}
    assert client.get("/api/admin/waitlist", headers=token("s@example.com", "staff password 123")).status_code == 403


def test_consent_text_is_published(client):
    assert "unsubscribe" in client.get("/api/waitlist/consent").json()["text"]
