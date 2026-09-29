"""Per-campaign results: CTR, CPC, CAC, ROAS, contribution after ads (Blueprint section I)."""
from app.models import Product
from app.services import admin as admin_svc
from app.services import campaigns

CUSTOMER = {"name": "Ann Ad", "email": "ann@example.com", "address": "1 Main St, London"}


def buy(client, campaign=None, pid="desk-mat"):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": pid})
    return client.post(f"/api/carts/{cid}/checkout", json={**CUSTOMER, "campaign": campaign}).json()


def owner(client, db):
    from app.services import auth
    with db() as s:
        auth.create_user(s, "owner@example.com", "a long owner password", "owner")
        s.commit()
    t = client.post("/api/admin/login", json={"email": "owner@example.com", "password": "a long owner password"}).json()["token"]
    return {"x-admin-token": t}


def test_normalise_tags():
    assert campaigns.normalise("Facebook", "Desk Reset Oct") == "facebook:desk-reset-oct"
    assert campaigns.normalise("", "x") is None
    assert campaigns.normalise("tiktok", None) == "tiktok:none"
    assert campaigns.parse_tag("Google:<script>alert(1)</script>") == "google:script-alert-1-script"
    assert campaigns.parse_tag("no-colon") is None


def test_campaign_report_math(client, db):
    h = owner(client, db)
    for _ in range(2):
        buy(client, "facebook:desk-reset")
    buy(client)  # direct
    client.post("/api/events", json={"type": "visit", "campaign": "facebook:desk-reset"})
    client.post("/api/events", json={"type": "visit", "campaign": "junk"})  # dropped: no valid tag
    r = client.post("/api/admin/campaigns/spend", headers=h, json={
        "campaign": "Facebook:Desk Reset", "day": "2099-01-01", "spend": 2000, "clicks": 50, "impressions": 2000})
    assert r.status_code == 201 and r.json()["campaign"] == "facebook:desk-reset"

    rep = client.get("/api/admin/campaigns", headers=h).json()
    fb = next(c for c in rep["campaigns"] if c["campaign"] == "facebook:desk-reset")
    direct = next(c for c in rep["campaigns"] if c["campaign"] == campaigns.DIRECT)
    with db() as s:
        unit = admin_svc.economics(s.get(Product, "desk-mat")).contribution_pre_ads
    assert fb["orders"] == 2 and fb["revenue"] == 2 * 3595  # £32 + £3.95 delivery each
    assert fb["visits"] == 1
    assert fb["ctr"] == 0.025 and fb["cpc"] == 40 and fb["cac"] == 1000
    assert fb["roas"] == round(7190 / 2000, 2)
    assert fb["contribution_pre_ads"] == 2 * unit
    assert fb["contribution_after_ads"] == 2 * unit - 2000
    assert direct["orders"] == 1 and direct["cac"] is None
    assert rep["label"] == "ESTIMATE"
    assert rep["campaigns"][-1]["campaign"] == campaigns.DIRECT  # direct listed last


def test_losing_campaign_is_flagged(client, db):
    h = owner(client, db)
    buy(client, "google:test")
    client.post("/api/admin/campaigns/spend", headers=h, json={"campaign": "google:test", "day": "2099-01-01", "spend": 50000})
    g = next(c for c in client.get("/api/admin/campaigns", headers=h).json()["campaigns"] if c["campaign"] == "google:test")
    assert g["contribution_after_ads"] < 0 and "Losing money" in g["verdict"]


def test_spend_needs_owner_and_valid_tag(client, db):
    h = owner(client, db)
    assert client.post("/api/admin/campaigns/spend", headers=h, json={"campaign": "nocolon", "day": "2099-01-01", "spend": 1}).status_code == 400
    assert client.post("/api/admin/campaigns/spend", headers=h, json={"campaign": "a:b", "day": "01/01/2099", "spend": 1}).status_code == 422
    assert client.post("/api/admin/campaigns/spend", headers=h, json={"campaign": "a:b", "day": "2099-01-01", "spend": -1}).status_code == 422
    assert client.get("/api/admin/campaigns").status_code in (401, 503)


def test_funnel_ignores_visits(client, db):
    h = owner(client, db)
    client.post("/api/events", json={"type": "visit", "campaign": "facebook:x"})
    steps = client.get("/api/admin/funnel", headers=h).json()["steps"]
    assert [s["type"] for s in steps] == ["view_product", "add_to_cart", "begin_checkout", "purchase"]
