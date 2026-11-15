"""Entrance TV setup and removal by the manager (spec §4.4, §11 step 5)."""

import re

from sqlalchemy import text

from app import admin
from tests.test_reasons import As


def manager(client, make_user, session_for):
    uid = make_user("Emeka Okonkwo", "manager")
    return uid, As(client, session_for, uid)


def tv_code(client):
    return client.get("/api/kiosk/code")


def actions(owner):
    with owner.connect() as conn:
        return conn.execute(text("SELECT action, actor_id FROM activity_log ORDER BY id")).all()


def test_manager_makes_a_single_use_tv_link_and_the_tv_pairs(client, make_user, session_for, owner):
    uid, m = manager(client, make_user, session_for)
    r = m.post("/api/kiosks")
    assert r.status_code == 200, r.text
    body = r.json()
    assert re.fullmatch(r"[A-Z2-9]{5}-[A-Z2-9]{5}", body["code"])
    assert body["link"] == f"https://attendance.test/tv/pair/{body['code']}"
    assert body["tv_page"] == "https://attendance.test/tv"
    assert body["expires"] == "Tue 17 Nov, 09:00"  # 24 hours
    with owner.connect() as conn:
        stored = conn.execute(text("SELECT setup_token_hash FROM kiosks")).scalar_one()
    assert body["code"].replace("-", "").encode() not in bytes(stored)

    listed = m.get("/api/kiosks").json()["tvs"]
    assert [(t["status"], t["label"]) for t in listed] == [("waiting", "Waiting for setup")]

    # Typed on the TV with its remote: lower case, without the dash, is fine.
    client.cookies.delete("att_session")
    assert client.post("/api/kiosk/pair", json={"token": body["code"].replace("-", "").lower()}).status_code == 200
    assert tv_code(client).status_code == 200
    # Single use.
    r = client.post("/api/kiosk/pair", json={"token": body["code"]})
    assert r.status_code == 410 and r.json()["detail"]["code"] == "pair_invalid"

    tv = m.get("/api/kiosks").json()
    assert [(t["status"], t["set_up"], t["last_seen"]) for t in tv["tvs"]] == [
        ("online", "09:00 today, Emeka", "09:00 today")]
    assert actions(owner) == [("kiosk_create", uid), ("kiosk_pair", None)]


def test_tv_shows_offline_when_not_seen_for_two_minutes(client, make_user, session_for, clock):
    _, m = manager(client, make_user, session_for)
    code = m.post("/api/kiosks").json()["code"]
    client.post("/api/kiosk/pair", json={"token": code})
    clock.advance(minutes=3)
    assert m.get("/api/kiosks").json()["tvs"][0]["label"] == "Offline"


def test_manager_removes_the_tv_and_it_stops_showing_codes(client, make_user, session_for, owner):
    uid, m = manager(client, make_user, session_for)
    code = m.post("/api/kiosks").json()["code"]
    client.post("/api/kiosk/pair", json={"token": code})
    assert tv_code(client).status_code == 200
    kiosk_id = m.get("/api/kiosks").json()["tvs"][0]["id"]

    assert m.post(f"/api/kiosks/{kiosk_id}/revoke").status_code == 200
    r = tv_code(client)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "kiosk_not_paired"
    assert m.get("/api/kiosks").json()["tvs"] == []
    assert m.post(f"/api/kiosks/{kiosk_id}/revoke").status_code == 404
    assert actions(owner)[-1] == ("kiosk_revoke", uid)


def test_an_unused_link_can_be_cancelled(client, make_user, session_for):
    _, m = manager(client, make_user, session_for)
    made = m.post("/api/kiosks").json()
    m.post(f"/api/kiosks/{made['id']}/revoke")
    assert client.post("/api/kiosk/pair", json={"token": made["code"]}).status_code == 410


def test_a_tv_link_expires_after_24_hours(client, make_user, session_for, clock):
    _, m = manager(client, make_user, session_for)
    code = m.post("/api/kiosks").json()["code"]
    clock.advance(hours=24, seconds=1)
    assert client.post("/api/kiosk/pair", json={"token": code}).status_code == 410
    assert m.get("/api/kiosks").json()["tvs"] == []


def test_a_wrong_code_is_refused(client):
    assert client.post("/api/kiosk/pair", json={"token": "ABCDE-FGHJK"}).status_code == 410


def test_cli_create_tv_link_still_works(client, capsys):
    admin.main(["create-tv-link"])
    out = capsys.readouterr().out.strip().splitlines()
    link = out[1]
    assert link.startswith("https://attendance.test/tv/pair/")
    assert "type the code" in out[2]
    assert client.post("/api/kiosk/pair", json={"token": link.rsplit("/", 1)[1]}).status_code == 200


def test_md_sees_tv_changes_in_the_activity_log(client, make_user, session_for, md):
    _, m = manager(client, make_user, session_for)
    made = m.post("/api/kiosks").json()
    m.post(f"/api/kiosks/{made['id']}/revoke")
    entries = As(client, session_for, md).get("/api/activity?filter=tv").json()["entries"]
    assert [(e["label"], e["details"]) for e in entries] == [
        ("TV removed", f"TV {made['id']}"), ("TV link created", f"TV {made['id']}")]
