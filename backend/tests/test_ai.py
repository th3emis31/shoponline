"""AI assistants (Blueprint section J): labelled drafts, approval gate, memory, call log, safe fallbacks."""
import pytest

from app.config import settings
from app.models import AICall, AIMemory, BusinessDecision, Product
from app.services.ai import agents, providers


def login(client, db, role="owner", email="owner@example.com"):
    from app.services import auth
    with db() as s:
        auth.create_user(s, email, "a long owner password", role)
        s.commit()
    t = client.post("/api/admin/login", json={"email": email, "password": "a long owner password"}).json()["token"]
    return {"x-admin-token": t}


def labelled(output: str) -> bool:
    claims = output.split(agents.DRAFT_MARK)[0].splitlines()
    return all(line.startswith(agents.LABELS) or line.startswith("HYPOTHESIS") for line in claims if line.strip())


@pytest.mark.parametrize("agent,subject", [
    ("research", ""), ("product", "desk-mat"), ("marketing", "cable-tray"), ("analytics", ""),
    ("inventory", ""), ("seo", "monitor-riser"),
])
def test_every_agent_works_free_with_labels(client, db, agent, subject):
    h = login(client, db)
    r = client.post("/api/admin/ai/run", headers=h, json={"agent": agent, "subject": subject})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["provider"] == "rules" and body["status"] == "draft"
    assert labelled(body["output"]), body["output"]
    assert "FACT:" in body["output"]


def test_customer_agent_drafts_reply_and_staff_may_use_it(client, db):
    client.post("/api/contact", json={"name": "Pat Lee", "email": "pat@example.com", "topic": "product",
                                      "message": "My riser arrived broken, what now?"})
    h = login(client, db, role="staff", email="staff@example.com")
    tid = client.get("/api/admin/support", headers=h).json()["tickets"][0]["id"]
    r = client.post("/api/admin/ai/run", headers=h, json={"agent": "customer", "subject": str(tid)}).json()
    draft = r["output"].split(agents.DRAFT_MARK)[1]
    assert "Hi Pat" in draft and "photo" in draft  # damaged template chosen
    # staff can't run other assistants or see the AI overview
    assert client.post("/api/admin/ai/run", headers=h, json={"agent": "product", "subject": "desk-mat"}).status_code == 403
    assert client.get("/api/admin/ai", headers=h).status_code == 403


def test_approval_records_decision_and_memory_and_changes_nothing(client, db):
    h = login(client, db)
    with db() as s:
        price_before = s.get(Product, "desk-mat").price
    task = client.post("/api/admin/ai/run", headers=h, json={"agent": "product", "subject": "desk-mat"}).json()
    r = client.post(f"/api/admin/ai/{task['id']}/decide", headers=h, json={"approve": True, "note": "Agree"})
    assert r.json()["status"] == "approved"
    assert client.post(f"/api/admin/ai/{task['id']}/decide", headers=h, json={"approve": False}).status_code == 409
    with db() as s:
        d = s.query(BusinessDecision).one()
        assert d.ai_task_id == task["id"] and d.reason == "Agree" and d.decided_by == "owner@example.com"
        assert s.get(AIMemory, "product:desk-mat") is not None
        assert s.get(Product, "desk-mat").price == price_before
    ov = client.get("/api/admin/ai", headers=h).json()
    assert ov["decisions"][0]["title"].startswith("Product")


def test_unknown_agent_and_missing_subject(client, db):
    h = login(client, db)
    assert client.post("/api/admin/ai/run", headers=h, json={"agent": "trader"}).status_code == 404
    assert client.post("/api/admin/ai/run", headers=h, json={"agent": "seo", "subject": "nope"}).status_code == 400


def test_unlabelled_ai_lines_become_hypotheses():
    out = agents.enforce_labels("FACT: price is £32\nThis will sell loads\n- **ESTIMATE:** 3% conversion\n"
                                f"{agents.DRAFT_MARK}\nHi there, thanks!")
    lines = out.splitlines()
    assert lines[0] == "FACT: price is £32"
    assert lines[1].startswith("HYPOTHESIS (unlabelled")
    assert lines[2] == "ESTIMATE: 3% conversion"
    assert lines[-1] == "Hi there, thanks!"  # draft text left as written


def test_unreachable_local_ai_falls_back_to_rules_and_is_logged(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:9")  # nothing listens here
    h = login(client, db)
    r = client.post("/api/admin/ai/run", headers=h, json={"agent": "analytics"}).json()
    assert r["provider"] == "rules" and r["error"] and "wasn't used" in r["output"]
    with db() as s:
        call = s.query(AICall).one()
        assert call.ok is False and call.provider == "ollama"


def test_external_api_gets_redacted_text_and_output_is_labelled(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "api")
    monkeypatch.setattr(settings, "ai_api_key", "k")
    monkeypatch.setattr(settings, "ai_model", "m")
    seen = {}

    def fake_post(url, body, headers, timeout=120):
        seen["text"] = body["messages"][1]["content"]
        return {"choices": [{"message": {"content": "FACT: ok\nsounds good\n" + agents.DRAFT_MARK + "\nHi Pat"}}]}

    monkeypatch.setattr(providers, "_post", fake_post)
    client.post("/api/contact", json={"name": "Pat Lee", "email": "pat@example.com", "topic": "other",
                                      "message": "Call me on 07700 900123 or pat@example.com, SW1A 1AA"})
    h = login(client, db)
    tid = client.get("/api/admin/support", headers=h).json()["tickets"][0]["id"]
    r = client.post("/api/admin/ai/run", headers=h, json={"agent": "customer", "subject": str(tid)}).json()
    assert r["provider"] == "api"
    assert "07700" not in seen["text"] and "pat@example.com" not in seen["text"] and "SW1A" not in seen["text"]
    assert "HYPOTHESIS (unlabelled" in r["output"]


def test_daily_limit_stops_paid_calls(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "api")
    monkeypatch.setattr(settings, "ai_api_key", "k")
    monkeypatch.setattr(settings, "ai_model", "m")
    monkeypatch.setattr(settings, "ai_max_calls_per_day", 0)
    monkeypatch.setattr(providers, "_post", lambda *a, **k: pytest.fail("must not call the paid API"))
    h = login(client, db)
    r = client.post("/api/admin/ai/run", headers=h, json={"agent": "inventory"}).json()
    assert r["provider"] == "rules" and "Daily AI limit" in r["error"]


def test_manual_decision_log(client, db):
    h = login(client, db)
    r = client.post("/api/admin/decisions", headers=h, json={"title": "Supplier for mats", "decision": "Use Supplier A",
                                                              "reason": "Best sample", "evidence": "Sample photos"})
    assert r.status_code == 201
    assert client.get("/api/admin/ai", headers=h).json()["decisions"][0]["title"] == "Supplier for mats"
