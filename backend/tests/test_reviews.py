"""Verified-purchase reviews: only real buyers, never suppressing negatives."""
from app.models import Order
from app.services import emails

CUSTOMER = {"name": "Jane Mary Doe", "email": "jane@example.com", "address": "1 Main St, London"}


def buy(client, pid="desk-mat"):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": pid})
    return client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER).json()


def token(order_id):
    return emails.sign("review:" + order_id)


def owner(client, db):
    from app.services import auth
    with db() as s:
        auth.create_user(s, "owner@example.com", "a long owner password", "owner")
        s.commit()
    t = client.post("/api/admin/login", json={"email": "owner@example.com", "password": "a long owner password"}).json()["token"]
    return {"x-admin-token": t}


def test_no_reviews_means_nothing_claimed(client):
    r = client.get("/api/products/desk-mat/reviews").json()
    assert r == {"count": 0, "average": None, "reviews": []}


def test_buyer_reviews_then_published_after_moderation(client, db):
    order = buy(client)
    form = client.get(f"/api/reviews/{order['id']}", params={"token": token(order["id"])}).json()
    assert form["display_name"] == "Jane D."  # never the full name
    assert form["items"] == [{"product_id": "desk-mat", "name": form["items"][0]["name"], "reviewed": False}]
    r = client.post(f"/api/reviews/{order['id']}", json={"token": token(order["id"]), "product_id": "desk-mat",
                                                         "rating": 2, "title": "Thin", "body": "Thinner than hoped."})
    assert r.status_code == 201
    # not public until checked
    assert client.get("/api/products/desk-mat/reviews").json()["count"] == 0
    h = owner(client, db)
    rid = client.get("/api/admin/reviews", headers=h).json()["reviews"][0]["id"]
    # a negative review can't be rejected without a valid reason
    bad = client.post(f"/api/admin/reviews/{rid}", json={"action": "reject", "reason": "negative"}, headers=h)
    assert bad.status_code == 400
    assert client.post(f"/api/admin/reviews/{rid}", json={"action": "publish"}, headers=h).json()["status"] == "published"
    pub = client.get("/api/products/desk-mat/reviews").json()
    assert pub["count"] == 1 and pub["average"] == 2.0 and pub["reviews"][0]["name"] == "Jane D."
    assert pub["reviews"][0]["verified"] is True
    audit = client.get("/api/admin/audit", headers=h).json()
    assert any(a["action"] == "review.publish" for a in audit)


def test_one_review_per_product_per_order(client):
    order = buy(client)
    body = {"token": token(order["id"]), "product_id": "desk-mat", "rating": 5}
    assert client.post(f"/api/reviews/{order['id']}", json=body).status_code == 201
    assert client.post(f"/api/reviews/{order['id']}", json=body).status_code == 409
    form = client.get(f"/api/reviews/{order['id']}", params={"token": token(order["id"])}).json()
    assert form["items"][0]["reviewed"] is True


def test_forged_or_foreign_links_are_refused(client):
    order = buy(client)
    assert client.get(f"/api/reviews/{order['id']}", params={"token": "x" * 32}).status_code == 404
    other = buy(client)
    # a valid token for one order does not open another
    assert client.get(f"/api/reviews/{other['id']}", params={"token": token(order["id"])}).status_code == 404
    # only products in the order
    r = client.post(f"/api/reviews/{order['id']}", json={"token": token(order["id"]), "product_id": "cable-clips", "rating": 5})
    assert r.status_code == 400
    # rating must be 1-5
    r = client.post(f"/api/reviews/{order['id']}", json={"token": token(order["id"]), "product_id": "desk-mat", "rating": 6})
    assert r.status_code == 422


def test_unpaid_orders_cannot_be_reviewed(client, db):
    order = buy(client)
    with db() as s:
        s.get(Order, order["id"]).status = "pending_payment"
        s.commit()
    r = client.get(f"/api/reviews/{order['id']}", params={"token": token(order["id"])})
    assert r.status_code == 409


def test_order_lookup_gives_buyer_their_review_link(client):
    order = buy(client)
    view = client.post(f"/api/orders/{order['id']}/lookup", json={"email": CUSTOMER["email"]}).json()
    assert view["review_path"] == f"/review/{order['id']}?token={token(order['id'])}"
    # checkout response itself (no email proof) doesn't include it
    assert order.get("review_path") is None


def test_reject_needs_listed_reason_and_hides_review(client, db):
    order = buy(client)
    client.post(f"/api/reviews/{order['id']}", json={"token": token(order["id"]), "product_id": "desk-mat",
                                                    "rating": 5, "body": "call me on 07700 900000"})
    h = owner(client, db)
    rid = client.get("/api/admin/reviews", headers=h).json()["reviews"][0]["id"]
    client.post(f"/api/admin/reviews/{rid}", json={"action": "publish"}, headers=h)
    r = client.post(f"/api/admin/reviews/{rid}", json={"action": "reject", "reason": "personal_data"}, headers=h)
    assert r.json()["status"] == "rejected"
    assert client.get("/api/products/desk-mat/reviews").json()["count"] == 0
