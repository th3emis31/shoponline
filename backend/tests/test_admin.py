import pytest

from app.models import AdminAudit, Order, Product

CUSTOMER = {"name": "Jane Doe", "email": "jane@example.com", "address": "1 Main St, London"}


@pytest.fixture()
def admin(client, admin_token):
    client.headers["X-Admin-Token"] = admin_token
    return client


def place(client, product_id="desk-mat", qty=1):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": product_id, "quantity": qty})
    return client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER).json()


def stock(db, pid):
    with db() as s:
        return s.get(Product, pid).stock


def test_admin_requires_token(client, admin_token):
    assert client.get("/api/admin/orders").status_code == 401
    assert client.get("/api/admin/orders", headers={"X-Admin-Token": "nope"}).status_code == 401


def test_admin_disabled_without_configured_token(client):
    assert client.get("/api/admin/orders", headers={"X-Admin-Token": ""}).status_code == 503


def test_list_and_ship_order(admin, db):
    order = place(admin)
    rows = admin.get("/api/admin/orders").json()
    assert rows[0]["id"] == order["id"]
    assert rows[0]["customer_email"] == "jane@example.com"
    assert rows[0]["next_statuses"] == ["cancelled", "shipped"]
    r = admin.post(f"/api/admin/orders/{order['id']}/status", json={"status": "shipped", "note": "Royal Mail"})
    assert r.status_code == 200 and r.json()["status"] == "shipped"
    assert admin.get("/api/admin/orders", params={"status": "shipped"}).json()[0]["id"] == order["id"]
    with db() as s:
        a = s.query(AdminAudit).one()
        assert a.action == "order.status" and '"new": "shipped"' in a.detail


def test_cancel_releases_stock_once(admin, db):
    order = place(admin, "monitor-riser", 2)
    assert stock(db, "monitor-riser") == 18
    assert admin.post(f"/api/admin/orders/{order['id']}/status", json={"status": "cancelled"}).status_code == 200
    assert stock(db, "monitor-riser") == 20
    # Second cancel is refused, so stock can't be released twice.
    assert admin.post(f"/api/admin/orders/{order['id']}/status", json={"status": "cancelled"}).status_code == 409
    assert stock(db, "monitor-riser") == 20


def test_paid_orders_cannot_be_cancelled_here(admin, db):
    order = place(admin)
    with db() as s:
        s.get(Order, order["id"]).status = "paid"
        s.commit()
    r = admin.post(f"/api/admin/orders/{order['id']}/status", json={"status": "cancelled"})
    assert r.status_code == 409 and "allowed: shipped" in r.json()["error"]


def test_invalid_status_and_missing_order(admin):
    order = place(admin)
    assert admin.post(f"/api/admin/orders/{order['id']}/status", json={"status": "teleported"}).status_code == 409
    assert admin.post("/api/admin/orders/nope/status", json={"status": "shipped"}).status_code == 404


def test_products_show_costs_and_economics(admin):
    rows = {p["id"]: p for p in admin.get("/api/admin/products").json()}
    mat = rows["desk-mat"]
    assert mat["landed_cost"] == 600 and mat["contribution_pre_ads"] == 1444
    assert round(mat["break_even_roas"], 2) == 2.22 and mat["label"] == "ESTIMATE"


def test_update_product_is_validated_and_audited(admin, db):
    r = admin.patch("/api/admin/products/desk-mat", json={"stock": 7, "price": 3400, "note": "restock"})
    assert r.status_code == 200 and r.json()["stock"] == 7 and r.json()["price"] == 3400
    assert admin.patch("/api/admin/products/desk-mat", json={"stock": -1}).status_code == 422
    assert admin.patch("/api/admin/products/desk-mat", json={"price": 0}).status_code == 422
    assert admin.patch("/api/admin/products/desk-mat", json={}).status_code == 400
    assert admin.patch("/api/admin/products/nope", json={"stock": 1}).status_code == 404
    log = admin.get("/api/admin/audit").json()
    assert log[0]["action"] == "product.update"
    assert log[0]["detail"]["before"] == {"stock": 50, "price": 3200}
    assert log[0]["detail"]["note"] == "restock"


def test_deactivated_product_hidden_from_shop(admin):
    admin.patch("/api/admin/products/cable-clips", json={"active": False})
    ids = [p["id"] for p in admin.get("/api/products").json()]
    assert "cable-clips" not in ids
    assert admin.get("/api/products/cable-clips").status_code == 404


def test_funnel_counts_and_rates(admin):
    for _ in range(4):
        assert admin.post("/api/events", json={"type": "view_product", "product_id": "desk-mat"}).status_code == 204
    admin.post("/api/events", json={"type": "add_to_cart", "product_id": "desk-mat"})
    admin.post("/api/events", json={"type": "add_to_cart", "product_id": "not-a-product"})
    admin.post("/api/events", json={"type": "begin_checkout"})
    place(admin)  # dev-mode checkout records a purchase server-side
    f = admin.get("/api/admin/funnel", params={"days": 7}).json()
    counts = {s["type"]: s["count"] for s in f["steps"]}
    assert counts == {"view_product": 4, "add_to_cart": 2, "begin_checkout": 1, "purchase": 1}
    assert f["steps"][1]["rate_from_previous"] == 0.5
    assert f["overall_conversion"] == 0.25


def test_browser_cannot_fake_purchases(client):
    assert client.post("/api/events", json={"type": "purchase"}).status_code == 422
    assert client.post("/api/events", json={"type": "whatever"}).status_code == 422
