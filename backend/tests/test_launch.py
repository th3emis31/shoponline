"""Launch checklist: the blueprint's 14 gates (section O)."""
from app.config import settings
from app.models import Product
from app.services import launch


def login(client, db):
    from app.services import auth
    with db() as s:
        auth.create_user(s, "owner@example.com", "a long owner password", "owner")
        s.commit()
    t = client.post("/api/admin/login", json={"email": "owner@example.com", "password": "a long owner password"}).json()["token"]
    return {"x-admin-token": t}


def gate(data, gid):
    return next(g for g in data["gates"] if g["id"] == gid)


def test_fourteen_gates_and_not_ready_by_default(client, db):
    h = login(client, db)
    data = client.get("/api/admin/launch", headers=h).json()
    assert data["total"] == 14 and data["ready"] is False
    assert [g["name"] for g in data["gates"]][:2] == ["Product validation", "Unit economics"]
    # support is built and nothing is overdue -> green without confirmation
    assert gate(data, "support")["passed"] is True


def test_owner_confirmation_alone_cannot_pass_a_failing_gate(client, db):
    h = login(client, db)
    with db() as s:
        s.get(Product, "desk-reset").landed_cost = 5000  # quote came in too high
        s.commit()
    data = client.post("/api/admin/launch/unit_economics", headers=h, json={"confirmed": True, "note": "quotes in"}).json()
    g = gate(data, "unit_economics")
    assert g["confirmed"] is True and g["passed"] is False  # margin under 40%


def test_unit_economics_gate_uses_real_costs(client, db):
    h = login(client, db)
    with db() as s:
        p = s.get(Product, "desk-reset")
        p.fulfilment, p.supplier_cost, p.supplier_name = "dropship", 1500, "Acme"
        s.commit()
    client.post("/api/admin/launch/unit_economics", headers=h, json={"confirmed": True})
    assert gate(client.get("/api/admin/launch", headers=h).json(), "unit_economics")["passed"] is True


def test_website_gate_needs_lighthouse_90(client, db):
    h = login(client, db)
    g = gate(client.post("/api/admin/launch/website", headers=h, json={"confirmed": True, "value": "84"}).json(), "website")
    assert g["passed"] is False and any("84" in c["text"] for c in g["checks"])
    g = gate(client.post("/api/admin/launch/website", headers=h, json={"confirmed": True, "value": "93"}).json(), "website")
    assert g["passed"] is True


def test_analytics_gate_needs_all_four_events(client, db):
    h = login(client, db)
    assert gate(client.get("/api/admin/launch", headers=h).json(), "analytics")["passed"] is False
    for t in ("view_product", "add_to_cart", "begin_checkout"):
        client.post("/api/events", json={"type": t})
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat"})
    client.post(f"/api/carts/{cid}/checkout", json={"name": "A", "email": "a@example.com", "address": "x"})
    assert gate(client.get("/api/admin/launch", headers=h).json(), "analytics")["passed"] is True


def test_unknown_gate_and_owner_only(client, db, monkeypatch):
    h = login(client, db)
    assert client.post("/api/admin/launch/nope", headers=h, json={"confirmed": True}).status_code == 404
    assert client.get("/api/admin/launch").status_code in (401, 503)
    audit = client.get("/api/admin/audit", headers=h).json()
    assert not any(a["action"].startswith("launch.") for a in audit)
    client.post("/api/admin/launch/shipping", headers=h, json={"confirmed": True, "note": "Royal Mail account"})
    assert any(a["action"] == "launch.confirm" for a in client.get("/api/admin/audit", headers=h).json())


def test_legal_gate_reads_business_details(client, db, monkeypatch):
    h = login(client, db)
    monkeypatch.setattr(settings, "shop_address", "1 High St, London")
    monkeypatch.setattr(settings, "shop_legal_name", "Novahaus Ltd")
    client.post("/api/admin/launch/legal_pages", headers=h, json={"confirmed": True, "note": "Solicitor reviewed"})
    assert gate(client.get("/api/admin/launch", headers=h).json(), "legal_pages")["passed"] is True
