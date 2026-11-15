"""Invites and Face ID sign-in (spec §4.1; decision D1)."""

from sqlalchemy import text

from tests.conftest import register_phone
from tests.softauthn import Phone

NOT_REGISTERED = "This phone isn't registered. Ask your manager to reset your phone."


def passkey_login(client, phone, **kw):
    opts = client.post("/api/auth/passkey/options").json()
    return client.post("/api/auth/passkey/login",
                       json={"challenge_id": opts["challenge_id"], "credential": phone.get(opts["options"], **kw)})


def test_invite_info(client, make_user, invite_for):
    token = invite_for(make_user("Adaeze Obi", "worker"))
    r = client.get(f"/api/invites/{token}")
    assert r.status_code == 200 and r.json()["name"] == "Adaeze Obi"
    assert client.get("/api/invites/not-a-real-token-at-all").status_code == 404


def test_registration_options_require_face_id_on_this_phone(client, make_user, invite_for):
    token = invite_for(make_user("Adaeze Obi", "worker"))
    o = client.post(f"/api/invites/{token}/options").json()["options"]
    sel = o["authenticatorSelection"]
    assert sel["authenticatorAttachment"] == "platform"
    assert sel["userVerification"] == "required"
    assert sel["residentKey"] == "required"
    assert o["rp"]["id"] == "attendance.test"


def test_register_creates_one_device_and_signs_in(client, make_user, invite_for, owner):
    uid = make_user("Adaeze Obi", "worker")
    r, _ = register_phone(client, invite_for(uid))
    assert r.status_code == 200
    assert client.get("/api/auth/me").json()["user"]["id"] == uid
    assert client.get("/api/me/today").status_code == 200
    with owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM devices WHERE revoked_at IS NULL")).scalar_one() == 1
        assert conn.execute(text("SELECT action FROM activity_log")).scalars().all() == ["device_register"]


def test_invite_works_only_once(client, make_user, invite_for):
    token = invite_for(make_user("Adaeze Obi", "worker"))
    opts = client.post(f"/api/invites/{token}/options").json()  # a second tab, opened earlier
    assert register_phone(client, token)[0].status_code == 200
    r = client.post(f"/api/invites/{token}/register", json={
        "challenge_id": opts["challenge_id"], "credential": Phone().create(opts["options"]), "privacy_ack": True})
    assert r.status_code == 410
    assert client.post(f"/api/invites/{token}/options").status_code == 410
    assert client.get(f"/api/invites/{token}").status_code == 410


def test_expired_invite_is_refused(client, make_user, invite_for, clock):
    token = invite_for(make_user("Adaeze Obi", "worker"))
    clock.advance(hours=48, seconds=1)
    assert client.post(f"/api/invites/{token}/options").status_code == 410


def test_privacy_notice_must_be_acknowledged(client, make_user, invite_for):
    token = invite_for(make_user("Adaeze Obi", "worker"))
    opts = client.post(f"/api/invites/{token}/options").json()
    r = client.post(f"/api/invites/{token}/register", json={
        "challenge_id": opts["challenge_id"], "credential": Phone().create(opts["options"]), "privacy_ack": False})
    assert r.status_code == 400


def test_registration_without_face_id_is_refused(client, make_user, invite_for):
    token = invite_for(make_user("Adaeze Obi", "worker"))
    r, _ = register_phone(client, token, uv=False)
    assert r.status_code == 400


def test_registration_from_another_website_is_refused(client, make_user, invite_for):
    token = invite_for(make_user("Adaeze Obi", "worker"))
    r, _ = register_phone(client, token, origin="https://evil.example")
    assert r.status_code == 400


def test_face_id_sign_in(client, registered):
    uid, phone, _ = registered()
    client.cookies.clear()
    r = passkey_login(client, phone)
    assert r.status_code == 200 and r.json()["user"]["id"] == uid
    assert "att_session=" in r.headers["set-cookie"]


def test_unregistered_phone_is_rejected(client, registered, owner):
    """Step 2 done check: an unregistered device can't sign in."""
    registered()
    client.cookies.clear()
    r = passkey_login(client, Phone())
    assert r.status_code == 401
    assert r.json()["detail"] == {"code": "phone_not_registered", "message": NOT_REGISTERED}
    with owner.connect() as conn:
        assert "login_failed" in conn.execute(text("SELECT action FROM activity_log")).scalars().all()


def test_revoked_phone_is_rejected(client, registered, owner):
    _, phone, _ = registered()
    with owner.begin() as conn:
        conn.execute(text("UPDATE devices SET revoked_at = now()"))
    client.cookies.clear()
    r = passkey_login(client, phone)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "phone_not_registered"


def test_sign_in_without_face_id_is_rejected(client, registered):
    _, phone, _ = registered()
    client.cookies.clear()
    assert passkey_login(client, phone, uv=False).status_code == 401


def test_sign_in_challenge_works_once(client, registered):
    _, phone, _ = registered()
    client.cookies.clear()
    opts = client.post("/api/auth/passkey/options").json()
    body = {"challenge_id": opts["challenge_id"], "credential": phone.get(opts["options"])}
    assert client.post("/api/auth/passkey/login", json=body).status_code == 200
    assert client.post("/api/auth/passkey/login", json=body).status_code == 400


def test_five_failed_face_id_sign_ins_lock_the_phone(client, registered, clock):
    _, phone, _ = registered()
    client.cookies.clear()
    for _ in range(5):
        assert passkey_login(client, phone, uv=False).status_code == 401
    assert passkey_login(client, phone).status_code == 429
    clock.advance(minutes=15, seconds=1)
    assert passkey_login(client, phone).status_code == 200


def test_new_registration_replaces_the_old_phone(client, make_user, invite_for, owner):
    uid = make_user("Adaeze Obi", "worker")
    _, old = register_phone(client, invite_for(uid))
    _, new = register_phone(client, invite_for(uid))
    client.cookies.clear()
    assert passkey_login(client, old).status_code == 401
    assert passkey_login(client, new).status_code == 200


def test_session_after_face_id_lasts_30_days(client, registered, clock):
    registered()
    clock.advance(days=29)
    assert client.get("/api/me/today").status_code == 200
    clock.advance(days=1, seconds=1)
    assert client.get("/api/me/today").status_code == 401


def test_md_cannot_be_invited(client, md, invite_for):
    assert client.get(f"/api/invites/{invite_for(md)}").status_code == 410

