"""Clock in and out from the TV (spec §4.2, §5, §12; decisions D1, D2)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app import codes

MASTER = b"test-master-secret-0123456789abcdef"
LAGOS = ZoneInfo("Africa/Lagos")


def lagos(h, m, s=0, day=16):
    return datetime(2026, 11, day, h, m, s, tzinfo=LAGOS)


def qr_at(t: datetime) -> str:
    unix = t.timestamp()
    return codes.qr_content(codes.day_secret(MASTER, t.astimezone(LAGOS).date()), codes.qr_window(unix))


def typed_at(t: datetime) -> str:
    unix = t.timestamp()
    return codes.typed_code(codes.day_secret(MASTER, t.astimezone(LAGOS).date()), codes.typed_window(unix))


def start(client, csrf, kind="in", code=None, method="qr", confirm=False, clock=None):
    if code is None:
        code = qr_at(clock.now())
    return client.post("/api/clock/start", headers={"X-CSRF-Token": csrf},
                       json={"kind": kind, "method": method, "code": code, "confirm": confirm})


def finish(client, csrf, started, phone, client_ms=2100, **kw):
    s = started.json()
    return client.post("/api/clock/finish", headers={"X-CSRF-Token": csrf}, json={
        "challenge_id": s["challenge_id"], "credential": phone.get(s["options"], **kw), "client_ms_to_scan": client_ms})


def clock_in_out(client, csrf, phone, clock, kind="in", **kw):
    st = start(client, csrf, kind, clock=clock, **kw)
    assert st.status_code == 200, st.text
    return finish(client, csrf, st, phone)


def attempts(owner):
    with owner.connect() as conn:
        return conn.execute(text("SELECT result, method FROM scan_attempts ORDER BY id")).all()


def test_clock_in_on_time_then_out(client, registered, clock, owner):
    _, phone, csrf = registered()
    clock.set(lagos(8, 4))
    r = clock_in_out(client, csrf, phone, clock)
    assert r.status_code == 200, r.text
    assert r.json() == {"kind": "in", "time": "08:04", "date": "Monday 16 November", "working_day": True,
                             "late_minutes": None, "left_early_minutes": None, "worked_minutes": None}
    clock.set(lagos(17, 2))
    r = clock_in_out(client, csrf, phone, clock, kind="out")
    assert r.status_code == 200
    assert r.json()["time"] == "17:02" and r.json()["worked_minutes"] == 8 * 60 + 58
    assert r.json()["left_early_minutes"] is None
    today = client.get("/api/me/today").json()
    assert today["clock_in"]["time"] == "08:04" and today["clock_out"]["time"] == "17:02"
    assert attempts(owner) == [("ok", "qr"), ("ok", "qr")]


def test_late_receipt(client, registered, clock):
    _, phone, csrf = registered()
    clock.set(lagos(8, 23))
    r = clock_in_out(client, csrf, phone, clock)
    assert r.json()["late_minutes"] == 23


def test_left_early_receipt(client, registered, clock):
    _, phone, csrf = registered()
    clock.set(lagos(8, 0))
    clock_in_out(client, csrf, phone, clock)
    clock.set(lagos(16, 15))
    assert clock_in_out(client, csrf, phone, clock, kind="out").json()["left_early_minutes"] == 45


def test_15_second_old_code_is_rejected(client, registered, clock, owner):
    """Step 2 done check."""
    _, phone, csrf = registered()
    clock.set(lagos(8, 0, 0))
    old = qr_at(clock.now())
    clock.advance(seconds=15)
    r = start(client, csrf, code=old)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "stale_code"
    assert attempts(owner) == [("stale_code", "qr")]


def test_previous_window_code_is_accepted(client, registered, clock):
    _, phone, csrf = registered()
    clock.set(lagos(8, 0, 0))
    code = qr_at(clock.now())
    clock.advance(seconds=9)
    assert start(client, csrf, code=code).status_code == 200


def test_typed_code_works_for_its_30_seconds_and_stale_one_is_rejected(client, registered, clock):
    _, phone, csrf = registered()
    clock.set(lagos(8, 0, 0))
    code = typed_at(clock.now())
    clock.advance(seconds=28)
    assert start(client, csrf, code=code, method="typed").status_code == 200
    clock.advance(seconds=12)  # 40 s after it appeared; it changed 10 s ago
    r = start(client, csrf, code=code, method="typed")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "stale_code"


def test_scan_time_is_when_the_code_was_checked(client, registered, clock):
    """Face ID taking a while must not make someone late."""
    _, phone, csrf = registered()
    clock.set(lagos(8, 9, 58))
    st = start(client, csrf, clock=clock)
    clock.advance(seconds=20)
    r = finish(client, csrf, st, phone)
    assert r.json()["time"] == "08:09" and r.json()["late_minutes"] is None


def test_second_clock_in_is_rejected(client, registered, clock):
    """Step 2 done check, and spec §12."""
    _, phone, csrf = registered()
    clock.set(lagos(8, 4))
    clock_in_out(client, csrf, phone, clock)
    clock.advance(minutes=1)
    r = start(client, csrf, clock=clock)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "already_clocked_in" and r.json()["detail"]["time"] == "08:04"


def test_clock_out_without_clock_in_is_rejected(client, registered, clock):
    _, phone, csrf = registered()
    r = start(client, csrf, kind="out", clock=clock)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_clocked_in"


def test_second_clock_out_is_rejected(client, registered, clock):
    _, phone, csrf = registered()
    clock.set(lagos(8, 0))
    clock_in_out(client, csrf, phone, clock)
    clock.set(lagos(17, 0))
    clock_in_out(client, csrf, phone, clock, kind="out")
    assert start(client, csrf, kind="out", clock=clock).status_code == 409


def test_clock_out_within_5_minutes_needs_confirm(client, registered, clock):
    _, phone, csrf = registered()
    clock.set(lagos(8, 0))
    clock_in_out(client, csrf, phone, clock)
    clock.advance(minutes=4)
    r = start(client, csrf, kind="out", clock=clock)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "confirm_needed"
    assert start(client, csrf, kind="out", clock=clock, confirm=True).status_code == 200


def test_face_id_is_needed_to_finish(client, registered, clock, owner):
    _, phone, csrf = registered()
    st = start(client, csrf, clock=clock)
    r = finish(client, csrf, st, phone, uv=False)
    assert r.status_code == 401
    assert client.get("/api/me/today").json()["clock_in"] is None
    assert attempts(owner)[-1] == ("face_id_failed", "qr")


def test_another_phone_cannot_finish(client, registered, clock):
    from tests.softauthn import Phone

    _, phone, csrf = registered()
    st = start(client, csrf, clock=clock)
    assert finish(client, csrf, st, Phone()).status_code == 401


def test_clock_challenge_works_once_and_expires(client, registered, clock):
    _, phone, csrf = registered()
    st = start(client, csrf, clock=clock)
    assert finish(client, csrf, st, phone).status_code == 200
    assert finish(client, csrf, st, phone).status_code == 400

    clock.set(lagos(17, 0))
    st = start(client, csrf, kind="out", clock=clock)
    clock.advance(minutes=2, seconds=1)
    assert finish(client, csrf, st, phone).status_code == 400


def test_not_logged_in_is_counted(client, owner):
    r = client.post("/api/clock/start", json={"kind": "in", "method": "qr", "code": "x"})
    assert r.status_code == 401
    assert attempts(owner) == [("not_logged_in", None)]


def test_md_cannot_clock_in(client, md, clock):
    from tests.conftest import login_md

    csrf = login_md(client).json()["csrf_token"]
    assert start(client, csrf, clock=clock).status_code == 403


def test_session_without_registered_phone_cannot_clock(client, make_user, session_for, clock):
    token, csrf = session_for(make_user("No Phone", "worker"))
    client.cookies.set("att_session", token)
    r = start(client, csrf, clock=clock)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "phone_not_registered"


def test_weekend_scans_are_recorded_without_late(client, registered, clock):
    _, phone, csrf = registered()
    clock.set(lagos(11, 0, day=22))  # Sunday
    r = clock_in_out(client, csrf, phone, clock)
    assert r.status_code == 200 and r.json()["working_day"] is False and r.json()["late_minutes"] is None


def test_manager_clocks_in_too(client, registered, clock):
    _, phone, csrf = registered("Emeka Okonkwo", "manager")
    assert clock_in_out(client, csrf, phone, clock).status_code == 200


# ---- The entrance TV ----

@pytest.fixture
def tv(client, clock, owner):
    """Pair a TV. Returns a TestClient with the kiosk cookie."""
    from fastapi.testclient import TestClient

    from app.security import new_token, token_hash

    token = new_token()
    with owner.begin() as conn:
        conn.execute(text("INSERT INTO kiosks (setup_token_hash, setup_expires_at, created_at) VALUES (:h, :e, :n)"),
                     {"h": token_hash(token), "e": clock.now() + timedelta(hours=24), "n": clock.now()})
    tv_client = TestClient(client.app, base_url="http://testserver")
    assert tv_client.post("/api/kiosk/pair", json={"token": token}).status_code == 200
    assert tv_client.post("/api/kiosk/pair", json={"token": token}).status_code == 410  # single use
    return tv_client


def test_unpaired_tv_gets_no_code(client):
    r = client.get("/api/kiosk/code")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "kiosk_not_paired"


def test_tv_shows_codes_that_phones_can_use(tv, client, registered, clock):
    _, phone, csrf = registered()
    clock.set(lagos(8, 4, 2))
    c = tv.get("/api/kiosk/code").json()
    assert c["qr"].startswith("ATT1.") and len(c["typed"]) == 6
    assert 0 < c["qr_ms_left"] <= 5000 and 0 < c["typed_ms_left"] <= 30000
    assert c["greeting"] == "Good morning" and c["date"] == "Mon 16 Nov" and c["time"] == "08:04"
    assert start(client, csrf, code=c["qr"]).status_code == 200
    assert start(client, csrf, code=c["typed"], method="typed").status_code == 200


def test_tv_shows_first_names_and_times_only(tv, client, registered, clock):
    _, phone, csrf = registered("Adaeze Obi")
    clock.set(lagos(8, 23))  # late, but the TV never says so
    clock_in_out(client, csrf, phone, clock)
    recent = tv.get("/api/kiosk/code").json()["recent"]
    assert [(r["name"], r["time"], r["kind"]) for r in recent] == [("Adaeze", "08:23", "in")]
    assert "late" not in str(recent).lower()


def test_revoked_tv_gets_no_code(tv, owner):
    with owner.begin() as conn:
        conn.execute(text("UPDATE kiosks SET revoked_at = now()"))
    assert tv.get("/api/kiosk/code").status_code == 401

