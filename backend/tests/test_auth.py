from datetime import datetime, timedelta, timezone

import pytest

from app.models import AdminAudit, AdminSession, AdminUser
from app.services import auth

OWNER = ("owner@example.com", "correct horse battery")
STAFF = ("staff@example.com", "staple paper clip 42")


@pytest.fixture()
def users(db):
    with db() as s:
        auth.create_user(s, OWNER[0], OWNER[1], "owner")
        auth.create_user(s, STAFF[0], STAFF[1], "staff")


def login(client, email, password):
    return client.post("/api/admin/login", json={"email": email, "password": password})


def hdr(token):
    return {"X-Admin-Token": token}


def test_password_hashing():
    h = auth.hash_password("a long enough password")
    assert h.startswith("scrypt$") and "a long enough password" not in h
    assert auth.verify_password("a long enough password", h)
    assert not auth.verify_password("wrong password here", h)
    assert not auth.verify_password("anything", "garbage")
    with pytest.raises(auth.AuthError):
        auth.hash_password("short")


def test_create_user_validation(db):
    with db() as s:
        auth.create_user(s, " Mixed@Example.com ", "a long enough password", "owner")
        assert s.query(AdminUser).one().email == "mixed@example.com"
        with pytest.raises(auth.AuthError, match="already exists"):
            auth.create_user(s, "mixed@example.com", "a long enough password", "staff")
        with pytest.raises(auth.AuthError, match="Role"):
            auth.create_user(s, "x@example.com", "a long enough password", "god")


def test_owner_login_and_full_access(client, users):
    r = login(client, *OWNER)
    assert r.status_code == 200 and r.json()["role"] == "owner"
    t = r.json()["token"]
    assert client.get("/api/admin/me", headers=hdr(t)).json() == {"actor": OWNER[0], "role": "owner"}
    for path in ("/api/admin/orders", "/api/admin/products", "/api/admin/funnel", "/api/admin/audit"):
        assert client.get(path, headers=hdr(t)).status_code == 200, path


def test_staff_is_limited_to_orders(client, users):
    t = login(client, *STAFF).json()["token"]
    assert client.get("/api/admin/orders", headers=hdr(t)).status_code == 200
    for path in ("/api/admin/products", "/api/admin/funnel", "/api/admin/audit",
                 "/api/admin/products/desk-mat/economics"):
        assert client.get(path, headers=hdr(t)).status_code == 403, path
    assert client.patch("/api/admin/products/desk-mat", json={"stock": 1}, headers=hdr(t)).status_code == 403


def test_actions_are_audited_with_the_actor(client, users, db):
    cid = client.post("/api/carts").json()["id"]
    client.post(f"/api/carts/{cid}/items", json={"product_id": "desk-mat"})
    order = client.post(f"/api/carts/{cid}/checkout",
                        json={"name": "J", "email": "j@example.com", "address": "x"}).json()
    t = login(client, *STAFF).json()["token"]
    client.post(f"/api/admin/orders/{order['id']}/status", json={"status": "shipped"}, headers=hdr(t))
    with db() as s:
        row = s.query(AdminAudit).filter_by(action="order.status").one()
        assert row.actor == STAFF[0]
        assert s.query(AdminAudit).filter_by(action="admin.login").count() == 1


def test_wrong_password_and_unknown_email_look_the_same(client, users):
    a = login(client, OWNER[0], "wrong password!!")
    b = login(client, "nobody@example.com", "wrong password!!")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_lockout_after_repeated_failures(client, users, db):
    for _ in range(auth.MAX_FAILED_ATTEMPTS):
        assert login(client, OWNER[0], "wrong password!!").status_code == 401
    r = login(client, *OWNER)  # right password, but locked
    assert r.status_code == 401 and "Too many" in r.json()["detail"]
    with db() as s:  # lock expires
        u = s.query(AdminUser).filter_by(email=OWNER[0]).one()
        u.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.commit()
    assert login(client, *OWNER).status_code == 200


def test_logout_and_expiry(client, users, db):
    t = login(client, *OWNER).json()["token"]
    assert client.post("/api/admin/logout", headers=hdr(t)).status_code == 204
    assert client.get("/api/admin/me", headers=hdr(t)).status_code == 401
    t2 = login(client, *OWNER).json()["token"]
    with db() as s:
        for sess in s.query(AdminSession).all():
            sess.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        s.commit()
    assert client.get("/api/admin/me", headers=hdr(t2)).status_code == 401


def test_disable_and_password_reset_end_sessions(client, users, db):
    t = login(client, *STAFF).json()["token"]
    with db() as s:
        auth.set_active(s, STAFF[0], False)
    assert client.get("/api/admin/me", headers=hdr(t)).status_code == 401
    assert login(client, *STAFF).status_code == 401
    with db() as s:
        auth.set_active(s, STAFF[0], True)
    t = login(client, *STAFF).json()["token"]
    with db() as s:
        auth.set_password(s, STAFF[0], "a brand new password")
    assert client.get("/api/admin/me", headers=hdr(t)).status_code == 401
    assert login(client, STAFF[0], "a brand new password").status_code == 200


def test_session_tokens_are_stored_hashed(client, users, db):
    t = login(client, *OWNER).json()["token"]
    with db() as s:
        stored = s.query(AdminSession).one().token_hash
    assert stored != t and len(stored) == 64


def test_shared_token_still_works_as_owner(client, admin_token, users):
    r = client.get("/api/admin/me", headers=hdr(admin_token))
    assert r.json() == {"actor": "admin-token", "role": "owner"}


def test_accounts_work_without_shared_token(client, users):
    # No ADMIN_TOKEN configured: accounts still work, bad tokens get 401 (not 503).
    assert client.get("/api/admin/orders", headers=hdr("nope")).status_code == 401
    t = login(client, *OWNER).json()["token"]
    assert client.get("/api/admin/orders", headers=hdr(t)).status_code == 200


def test_cli_create_list_disable(db, monkeypatch, capsys):
    import app.admin_users as cli
    monkeypatch.setattr(cli, "SessionLocal", db)
    monkeypatch.setattr(cli, "inspect", lambda _e: type("I", (), {"has_table": lambda self, n: True})())
    monkeypatch.setenv("ADMIN_PASSWORD", "cli created password")
    assert cli.main(["create", "boss@example.com", "--role", "owner"]) == 0
    cli.main(["list"])
    assert "boss@example.com" in capsys.readouterr().out
    cli.main(["disable", "boss@example.com"])
    cli.main(["list"])
    assert "DISABLED" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="already exists"):
        cli.main(["create", "boss@example.com"])


def test_cli_password_prompt_retries(monkeypatch, capsys):
    import app.admin_users as cli
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    answers = iter(["short", "long enough pass", "different pass!!", "long enough pass", "long enough pass"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))
    assert cli._ask_password() == "long enough pass"
    out = capsys.readouterr().out
    assert "Too short: that was 5 characters" in out and "didn't match" in out
    answers2 = iter(["x"] * 3)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers2))
    with pytest.raises(SystemExit, match="Nothing was changed"):
        cli._ask_password()
