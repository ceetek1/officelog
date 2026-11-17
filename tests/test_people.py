"""People: add a worker, deactivate, reset a lost phone."""

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app import admin
from app.passkeys import NOT_REGISTERED
from tests.conftest import register_phone
from tests.softauthn import Phone
from tests.test_invites_passkeys import passkey_login
from tests.test_reasons import As, add_scan, lagos

MON = date(2026, 11, 16)


@pytest.fixture
def team(client, make_user, session_for, md):
    """The manager (signed in through ``As``) and a worker who registered a phone through an invite."""
    mgr = make_user("Emeka Okonkwo", "manager")
    manager = As(client, session_for, mgr)
    r = manager.post("/api/people", {"name": "Adaeze Obi"})
    assert r.status_code == 200, r.text
    worker_id, link = r.json()["id"], r.json()["link"]
    reg, phone = register_phone(client, link.rsplit("/", 1)[1])
    assert reg.status_code == 200, reg.text
    worker_cookie = reg.cookies["att_session"]
    client.cookies.delete("att_session")
    return {"mgr": mgr, "manager": manager, "worker": worker_id, "phone": phone, "worker_cookie": worker_cookie,
            "md": As(client, session_for, md)}


def actions(owner):
    with owner.connect() as conn:
        return conn.execute(text("SELECT action, actor_id, after FROM activity_log ORDER BY id")).all()


def token_of(link: str) -> str:
    return link.rsplit("/", 1)[1]


# ---- add a worker ----

def test_manager_adds_a_worker_and_gets_a_single_use_invite(client, make_user, session_for, owner, clock):
    mgr = make_user("Emeka Okonkwo", "manager")
    manager = As(client, session_for, mgr)
    r = manager.post("/api/people", {"name": "  Bisi   Ogunleye "})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Bisi Ogunleye"
    assert body["link"].startswith("https://attendance.test/invite/")
    assert body["expires"] == "Wed 18 Nov, 09:00"  # 48 hours from Monday 09:00 in Lagos
    token = token_of(body["link"])
    assert len(token) >= 43
    with owner.connect() as conn:
        role, created_by, lifetime, stored = conn.execute(text(
            "SELECT u.role, i.created_by, i.expires_at - i.created_at, i.token_hash "
            "FROM invites i JOIN users u ON u.id = i.user_id")).one()
    assert (role, created_by, lifetime) == ("worker", mgr, timedelta(hours=48))
    assert token.encode() not in bytes(stored)  # only the SHA-256 is stored
    info = client.get(f"/api/invites/{token}").json()
    assert info["name"] == "Bisi Ogunleye" and info["invited_by"] == "Emeka Okonkwo"
    assert [(a, actor) for a, actor, _ in actions(owner)] == [("user_add", mgr), ("invite_create", mgr)]
    # Single use.
    assert register_phone(client, token)[0].status_code == 200
    assert client.post(f"/api/invites/{token}/options").status_code == 410


def invite_dead(client, token):
    return client.post(f"/api/invites/{token}/options").status_code == 410


def test_a_name_is_needed(client, make_user, session_for):
    manager = As(client, session_for, make_user("Emeka Okonkwo", "manager"))
    r = manager.post("/api/people", {"name": "   "})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "name_needed"


def test_people_list_shows_where_each_phone_stands(team, client, make_user, clock):
    m = team["manager"]
    m.post("/api/people", {"name": "Bisi Ogunleye"})
    make_user("Yusuf Garba", "worker", active=False)
    people = {p["name"]: p for p in m.get("/api/people").json()["people"]}
    assert people["Adaeze Obi"]["label"] == "Active"
    assert people["Bisi Ogunleye"]["label"] == "Invited"
    assert people["Bisi Ogunleye"]["invite_expires"] == "Wed 18 Nov, 09:00"
    assert people["Yusuf Garba"]["label"] == "Off"
    assert people["Emeka Okonkwo"]["is_me"] is True
    assert list(people)[-1] == "Yusuf Garba"  # deactivated people last
    clock.advance(hours=49)
    people = {p["name"]: p for p in m.get("/api/people").json()["people"]}
    assert people["Bisi Ogunleye"]["label"] == "Expired"
    assert m.get("/api/people").json()["active_count"] == 3


# ---- reset phone: the Step 5 done check ----

def test_reset_phone_old_phone_cant_sign_in_new_invite_works_and_md_sees_it(team, client, owner):
    m, uid = team["manager"], team["worker"]
    r = m.post(f"/api/people/{uid}/reset-phone")
    assert r.status_code == 200, r.text
    new_link = r.json()["link"]

    # The reset phone can't sign in.
    client.cookies.clear()
    r = passkey_login(client, team["phone"])
    assert r.status_code == 401
    assert r.json()["detail"] == {"code": "phone_not_registered", "message": NOT_REGISTERED}
    # Its old session is signed out too.
    client.cookies.delete("att_session")
    client.cookies.set("att_session", team["worker_cookie"])
    assert client.get("/api/me/today").status_code == 401

    # The new invite works on a new phone, which can then sign in.
    reg, new_phone = register_phone(client, token_of(new_link), Phone())
    assert reg.status_code == 200, reg.text
    client.cookies.clear()
    r = passkey_login(client, new_phone)
    assert r.status_code == 200 and r.json()["user"]["id"] == uid

    # The reset is in the activity log, with who did it, and the MD sees it under "Phone resets".
    log = actions(owner)
    reset = [a for a in log if a[0] == "device_reset"]
    assert len(reset) == 1 and reset[0][1] == team["mgr"] and reset[0][2]["user_id"] == uid
    entries = team["md"].get("/api/activity?filter=resets").json()["entries"]
    assert any(e["label"] == "Phone reset" and e["details"] == "Adaeze Obi" and e["who"] == "Emeka Okonkwo"
               for e in entries)


def test_reset_cancels_the_old_unused_invite(client, make_user, session_for):
    m = As(client, session_for, make_user("Emeka Okonkwo", "manager"))
    r = m.post("/api/people", {"name": "Bisi Ogunleye"}).json()
    old = token_of(r["link"])
    new = token_of(m.post(f"/api/people/{r['id']}/reset-phone").json()["link"])
    assert invite_dead(client, old)
    assert register_phone(client, new)[0].status_code == 200


def test_manager_cant_reset_or_deactivate_themselves_or_the_md(team, md):
    m = team["manager"]
    for action in ("reset-phone", "deactivate"):
        r = m.post(f"/api/people/{team['mgr']}/{action}")
        assert r.status_code == 409 and r.json()["detail"]["code"] == "not_yourself"
        assert m.post(f"/api/people/{md}/{action}").status_code == 404
        assert m.post(f"/api/people/999999/{action}").status_code == 404


# ---- deactivate ----

def test_deactivated_person_cant_sign_in_or_scan_is_off_team_and_history_is_kept(team, client, owner, clock):
    m, uid = team["manager"], team["worker"]
    add_scan(owner, uid, "in", MON - timedelta(days=3), 8, 2)  # last Friday
    r = m.post(f"/api/people/{uid}/deactivate")
    assert r.status_code == 200 and r.json()["active"] is False

    client.cookies.clear()
    r = passkey_login(client, team["phone"])
    assert r.status_code == 401 and r.json()["detail"]["code"] == "phone_not_registered"
    client.cookies.delete("att_session")
    client.cookies.set("att_session", team["worker_cookie"])
    assert client.get("/api/me/today").status_code == 401
    r = client.post("/api/clock/start", json={"kind": "in", "method": "typed", "code": "123456"})
    assert r.status_code == 401

    clock.set(lagos(MON, 9, 0))
    assert uid not in [p["user_id"] for p in m.get("/api/team/today").json()["people"]]
    with owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM scans WHERE user_id = :u"), {"u": uid}).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM sessions WHERE user_id = :u AND revoked_at IS NULL"),
                            {"u": uid}).scalar_one() == 0
    deact = [a for a in actions(owner) if a[0] == "user_deactivate"]
    assert len(deact) == 1 and deact[0][1] == team["mgr"] and deact[0][2]["user_id"] == uid
    entries = team["md"].get("/api/activity?filter=people").json()["entries"]
    assert entries[0]["label"] == "Person deactivated" and entries[0]["details"] == "Adaeze Obi"

    # Can't be deactivated twice, or reset, and isn't offered paper time.
    assert m.post(f"/api/people/{uid}/deactivate").status_code == 409
    assert m.post(f"/api/people/{uid}/reset-phone").status_code == 409


def test_deactivated_person_cant_use_an_open_invite(client, make_user, session_for):
    m = As(client, session_for, make_user("Emeka Okonkwo", "manager"))
    r = m.post("/api/people", {"name": "Bisi Ogunleye"}).json()
    m.post(f"/api/people/{r['id']}/deactivate")
    assert invite_dead(client, token_of(r["link"]))


# ---- admin command line ----

def test_cli_create_worker_still_works(client, capsys):
    admin.main(["create-worker", "--name", "Adaeze Obi"])
    link = capsys.readouterr().out.strip().splitlines()[-1]
    assert register_phone(client, token_of(link))[0].status_code == 200


def test_cli_reset_phone_for_the_manager(client, make_user, invite_for, capsys, owner):
    """The manager can't reset their own phone on the People screen, so the developer can."""
    mgr = make_user("Emeka Okonkwo", "manager")
    _, old_phone = register_phone(client, invite_for(mgr))
    admin.main(["reset-phone", "--name", "emeka okonkwo"])
    link = capsys.readouterr().out.strip().splitlines()[-1]
    client.cookies.clear()
    assert passkey_login(client, old_phone).status_code == 401
    assert register_phone(client, token_of(link))[0].status_code == 200
    with owner.connect() as conn:
        assert "device_reset" in conn.execute(text("SELECT action FROM activity_log")).scalars().all()


def test_cli_reset_phone_needs_a_known_name(capsys):
    with pytest.raises(SystemExit):
        admin.main(["reset-phone", "--name", "Nobody"])
    assert "no active worker or manager" in capsys.readouterr().err
