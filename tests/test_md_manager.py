"""The MD adds the manager and can make a new invite for them, from the MD web pages."""

from datetime import timedelta

from sqlalchemy import text

from tests.conftest import login_md, register_phone
from tests.softauthn import Phone
from tests.test_invites_passkeys import passkey_login
from tests.test_reasons import As


def token_of(link: str) -> str:
    return link.rsplit("/", 1)[1]


def actions(owner):
    with owner.connect() as conn:
        return conn.execute(text("SELECT action, actor_id, after FROM activity_log ORDER BY id")).all()


def test_md_adds_the_manager_whose_invite_sets_up_face_id(client, md, session_for, owner):
    m = As(client, session_for, md)
    assert m.get("/api/md/manager").json() == {"manager": None}
    r = m.post("/api/md/manager", {"name": "  Emeka   Okonkwo "})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Emeka Okonkwo" and body["expires"] == "Wed 18 Nov, 09:00"
    assert body["link"].startswith("https://attendance.test/invite/")
    with owner.connect() as conn:
        role, active, created_by, lifetime = conn.execute(text(
            "SELECT u.role, u.active, i.created_by, i.expires_at - i.created_at FROM users u "
            "JOIN invites i ON i.user_id = u.id")).one()
    assert (role, active, created_by, lifetime) == ("manager", True, md, timedelta(hours=48))
    assert [(a, actor) for a, actor, _ in actions(owner)] == [("user_add", md), ("invite_create", md)]
    assert actions(owner)[0][2]["role"] == "manager"

    status = m.get("/api/md/manager").json()["manager"]
    assert (status["name"], status["status"], status["label"], status["invite_expires"]) == (
        "Emeka Okonkwo", "invited", "Invite waiting", "Wed 18 Nov, 09:00")

    reg, _ = register_phone(client, token_of(body["link"]))
    assert reg.status_code == 200 and reg.json()["user"]["role"] == "manager"
    assert m.get("/api/md/manager").json()["manager"]["label"] == "Phone set up"


def test_a_second_manager_is_refused(client, md, session_for, make_user, owner):
    make_user("Emeka Okonkwo", "manager")
    r = As(client, session_for, md).post("/api/md/manager", {"name": "Someone Else"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "manager_exists"
    assert "Emeka Okonkwo is already the manager" in r.json()["detail"]["message"]
    with owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM users WHERE role = 'manager'")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM activity_log")).scalar_one() == 0


def test_a_name_is_needed(client, md, session_for):
    r = As(client, session_for, md).post("/api/md/manager", {"name": "   "})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "name_needed"


def test_only_the_md_may_add_or_reinvite_the_manager(client, md, session_for, make_user):
    mgr = make_user("Emeka Okonkwo", "manager")
    for who in (mgr, make_user("Adaeze Obi", "worker")):
        u = As(client, session_for, who)
        for path, body in (("/api/md/manager", {"name": "X Y"}), ("/api/md/manager/new-invite", None)):
            r = u.post(path, body)
            assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden", (who, path)
        assert u.get("/api/md/manager").status_code == 403
    client.cookies.clear()
    assert client.post("/api/md/manager", json={"name": "X Y"}).status_code == 401


def test_md_posts_need_the_csrf_token(client, md):
    login_md(client)
    r = client.post("/api/md/manager", json={"name": "Emeka Okonkwo"})  # no X-CSRF-Token header
    assert r.status_code == 403 and r.json()["detail"]["code"] == "csrf"
    csrf = client.get("/api/auth/me").json()["csrf_token"]
    r = client.post("/api/md/manager", json={"name": "Emeka Okonkwo"}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200


def test_new_invite_link_resets_the_managers_phone(client, md, session_for, owner):
    m = As(client, session_for, md)
    first = m.post("/api/md/manager", {"name": "Emeka Okonkwo"}).json()
    reg, old_phone = register_phone(client, token_of(first["link"]))
    old_cookie = reg.cookies["att_session"]

    r = m.post("/api/md/manager/new-invite")
    assert r.status_code == 200, r.text
    new = r.json()
    assert new["name"] == "Emeka Okonkwo" and new["link"] != first["link"]
    assert m.get("/api/md/manager").json()["manager"]["label"] == "Invite waiting"

    # The old phone and its session stop working; the new invite sets up the new phone.
    client.cookies.clear()
    assert passkey_login(client, old_phone).json()["detail"]["code"] == "phone_not_registered"
    client.cookies.set("att_session", old_cookie)
    assert client.get("/api/me/today").status_code == 401
    client.cookies.clear()
    assert register_phone(client, token_of(new["link"]), Phone())[0].status_code == 200

    log = [(a, actor) for a, actor, _ in actions(owner)]
    assert ("device_reset", md) in log and log.count(("invite_create", md)) == 2
    entries = As(client, session_for, md).get("/api/activity?filter=resets").json()["entries"]
    assert any(e["label"] == "Phone reset" and e["details"] == "Emeka Okonkwo" and e["who"] == "Folake Adeyemi"
               for e in entries)


def test_new_invite_when_the_first_one_expired(client, md, session_for, clock):
    m = As(client, session_for, md)
    first = m.post("/api/md/manager", {"name": "Emeka Okonkwo"}).json()
    clock.advance(hours=49)
    assert m.get("/api/md/manager").json()["manager"]["label"] == "Invite expired"
    new = m.post("/api/md/manager/new-invite").json()
    assert client.post(f"/api/invites/{token_of(first['link'])}/options").status_code == 410
    assert register_phone(client, token_of(new["link"]))[0].status_code == 200


def test_new_invite_with_no_manager(client, md, session_for):
    r = As(client, session_for, md).post("/api/md/manager/new-invite")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "no_manager"


def test_cli_create_manager_still_refuses_a_second(capsys):
    """The admin command now uses the same code as the MD page."""
    import pytest

    from app import admin

    admin.main(["create-manager", "--name", "Emeka Okonkwo"])
    with pytest.raises(SystemExit):
        admin.main(["create-manager", "--name", "Someone Else"])
    assert "exactly one" in capsys.readouterr().err
