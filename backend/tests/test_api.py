from app.models import Product

CUSTOMER = {"name": "Jane Doe", "email": "jane@example.com", "address": "1 Main St, London"}


def new_cart(client):
    return client.post("/api/carts").json()["id"]


def test_products_hide_internal_costs(client):
    r = client.get("/api/products")
    assert r.status_code == 200
    assert len(r.json()) == 5
    for p in r.json():
        assert set(p) == {"id", "name", "price", "is_bundle", "in_stock"}
    assert client.get("/api/products/nope").status_code == 404


def test_cart_totals_and_shipping(client):
    cid = new_cart(client)
    r = client.post(f"/api/carts/{cid}/items", json={"product_id": "cable-clips", "quantity": 1})
    assert r.json()["subtotal"] == 1800
    assert r.json()["shipping"] == 395
    assert r.json()["total"] == 2195
    r = client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat", "quantity": 1})
    assert r.json()["subtotal"] == 5000
    assert r.json()["shipping"] == 0  # free over threshold
    r = client.delete(f"/api/carts/{cid}/items/desk-mat")
    assert len(r.json()["items"]) == 1


def test_add_item_validation(client):
    cid = new_cart(client)
    assert client.post(f"/api/carts/{cid}/items", json={"product_id": "nope"}).status_code == 404
    assert client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat", "quantity": 0}).status_code == 422
    assert client.post(f"/api/carts/{cid}/items", json={"product_id": "monitor-riser", "quantity": 21}).status_code == 409
    assert client.post("/api/carts/missing/items", json={"product_id": "desk-mat"}).status_code == 404


def test_checkout_flow_and_order_tracking(client, db):
    cid = new_cart(client)
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-reset", "quantity": 2})
    r = client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER)
    assert r.status_code == 201
    order = r.json()
    assert order["total"] == 15000 and order["shipping"] == 0
    with db() as s:
        assert s.get(Product, "desk-reset").stock == 18
    assert client.get(f"/api/carts/{cid}").status_code == 404
    assert client.get(f"/api/orders/{order['id']}", params={"email": "JANE@example.com"}).status_code == 200
    assert client.get(f"/api/orders/{order['id']}", params={"email": "other@example.com"}).status_code == 404


def test_checkout_validation(client):
    cid = new_cart(client)
    assert client.post(f"/api/carts/{cid}/checkout", json=CUSTOMER).json()["error"] == "Cart is empty"
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat"})
    assert client.post(f"/api/carts/{cid}/checkout", json={**CUSTOMER, "email": "bad"}).status_code == 422
    assert client.post(f"/api/carts/{cid}/checkout", json={**CUSTOMER, "name": "  "}).status_code == 422


def test_failed_checkout_is_all_or_nothing(client, db):
    a, b = new_cart(client), new_cart(client)
    client.post(f"/api/carts/{a}/items", json={"product_id": "desk-mat", "quantity": 1})
    client.post(f"/api/carts/{a}/items", json={"product_id": "monitor-riser", "quantity": 20})
    client.post(f"/api/carts/{b}/items", json={"product_id": "monitor-riser", "quantity": 1})
    assert client.post(f"/api/carts/{b}/checkout", json=CUSTOMER).status_code == 201
    assert client.post(f"/api/carts/{a}/checkout", json=CUSTOMER).status_code == 409
    with db() as s:
        assert s.get(Product, "desk-mat").stock == 50  # untouched
        assert s.get(Product, "monitor-riser").stock == 19


def test_admin_economics_fails_closed(client):
    assert client.get("/api/admin/products/desk-mat/economics").status_code == 503


def test_admin_economics(client, admin_token):
    url = "/api/admin/products/desk-mat/economics"
    assert client.get(url, headers={"X-Admin-Token": "wrong"}).status_code == 401
    r = client.get(url, headers={"X-Admin-Token": admin_token}, params={"cac": 1000})
    assert r.status_code == 200
    assert r.json()["contribution_pre_ads"] == 1444
    assert r.json()["contribution_post_ads"] == 444
    assert r.json()["label"] == "ESTIMATE"
