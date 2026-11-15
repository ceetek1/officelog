from datetime import timedelta

from sqlalchemy import text

from tests.conftest import MD_EMAIL, MD_PASSWORD, login_md


def test_md_logs_in_with_email_and_password(client, md):
    r = login_md(client, email="  FOLAKE@company.test ")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "md" and body["user"]["name"] == "Folake Adeyemi"
    cookie = r.headers["set-cookie"].lower()
    assert "att_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    me = client.get("/api/auth/me").json()
    assert me["user"]["id"] == md and me["csrf_token"] == body["csrf_token"]


def test_session_token_is_stored_only_as_a_hash(client, md, owner):
    login_md(client)
    token = client.cookies.get("att_session")
    with owner.connect() as conn:
        stored = conn.execute(text("SELECT token_hash FROM sessions")).scalar_one()
    assert token.encode() not in bytes(stored)
    assert len(bytes(stored)) == 32


def test_wrong_password_is_rejected_and_logged(client, md, owner):
    r = login_md(client, password="nope")
    assert r.status_code == 401
    assert r.json()["detail"]["message"] == "Wrong email or password."
    r = login_md(client, email="nobody@company.test")
    assert r.status_code == 401
    with owner.connect() as conn:
        actions = conn.execute(text("SELECT action, entity_id FROM activity_log ORDER BY id")).all()
    assert actions == [("login_failed", MD_EMAIL), ("login_failed", "nobody@company.test")]


def test_inactive_md_cannot_log_in(client, make_user):
    make_user("Old MD", "md", "old@company.test", MD_PASSWORD, active=False)
    assert login_md(client, email="old@company.test").status_code == 401


def test_five_failures_lock_the_email_for_15_minutes(client, md, clock):
    for _ in range(5):
        assert login_md(client, password="wrong").status_code == 401
    r = login_md(client)  # right password, but locked
    assert r.status_code == 429
    assert "Too many tries" in r.json()["detail"]["message"]
    clock.advance(minutes=14)
    assert login_md(client).status_code == 429
    clock.advance(minutes=1, seconds=1)
    assert login_md(client).status_code == 200


def test_logout_needs_csrf_then_ends_the_session(client, md):
    csrf = login_md(client).json()["csrf_token"]
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/auth/me").json()["user"] is None


def test_revoked_session_cookie_cannot_be_reused(client, md):
    csrf = login_md(client).json()["csrf_token"]
    token = client.cookies.get("att_session")
    client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    client.cookies.set("att_session", token)
    assert client.get("/api/auth/me").json()["user"] is None


def test_session_lasts_30_days(client, md, clock):
    login_md(client)
    clock.advance(days=29, hours=23)
    assert client.get("/api/auth/me").json()["user"] is not None
    clock.advance(hours=1)
    assert client.get("/api/auth/me").json()["user"] is None


def test_deactivated_user_session_stops_working(client, make_user, session_for, owner):
    uid = make_user("Adaeze Obi", "worker")
    token, _ = session_for(uid)
    client.cookies.set("att_session", token)
    assert client.get("/api/me/today").status_code == 200
    with owner.begin() as conn:
        conn.execute(text("UPDATE users SET active = false WHERE id = :u"), {"u": uid})
    assert client.get("/api/me/today").status_code == 401


def test_cookie_is_secure_in_production(monkeypatch, md):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    try:
        with TestClient(create_app(), base_url="https://testserver") as c:
            r = login_md(c)
            assert "secure" in r.headers["set-cookie"].lower()
            assert r.headers["strict-transport-security"].startswith("max-age=")
    finally:
        get_settings.cache_clear()
