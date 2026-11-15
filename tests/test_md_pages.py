"""The MD's Today board, history per person, and the privacy notice (spec §7, §10, §11 step 6)."""

from datetime import date

from sqlalchemy import text

from tests.test_reasons import As, add_scan, lagos

MON, FRI = date(2026, 11, 16), date(2026, 11, 13)


def setup(owner, make_user, session_for, client, md, clock):
    ids = {"M": make_user("Emeka Okonkwo", "manager"), "A": make_user("Adaeze Obi", "worker"),
           "B": make_user("Bola Ade", "worker"), "X": make_user("Gone Person", "worker", active=False)}
    with owner.begin() as conn:
        conn.execute(text("UPDATE users SET created_at = :t"), {"t": lagos(date(2026, 11, 2), 9, 0)})
    clock.set(lagos(MON, 9, 0))
    return ids, As(client, session_for, md)


def test_md_today_board_for_today_and_an_earlier_day(owner, make_user, session_for, client, md, clock):
    ids, m = setup(owner, make_user, session_for, client, md, clock)
    add_scan(owner, ids["A"], "in", MON, 8, 23)
    add_scan(owner, ids["M"], "in", MON, 7, 58)
    add_scan(owner, ids["B"], "in", FRI, 7, 50)
    add_scan(owner, ids["B"], "out", FRI, 17, 2)
    r = m.get("/api/md/today")
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["is_today"] is True and t["date"] == "Monday 16 November" and t["active_people"] == 3
    assert t["counts"]["on_time"] == 1 and t["counts"]["late"] == 1 and t["counts"]["not_in_yet"] == 1
    assert [p["name"] for p in t["people"]] == ["Bola Ade", "Emeka Okonkwo", "Adaeze Obi"]
    assert t["tv"] is None  # no TV set up yet

    f = m.get("/api/md/today?date=2026-11-13").json()
    assert f["is_today"] is False and f["short_date"] == "Fri 13 Nov"
    bola = next(p for p in f["people"] if p["name"] == "Bola Ade")
    assert bola["clock_out"]["time"] == "17:02" and bola["worked_minutes"] == 552
    assert f["counts"]["absent"] == 2  # Adaeze and the manager didn't come on Friday
    assert m.get("/api/md/today?date=2026-11-17").status_code == 400
    assert m.get("/api/md/today?date=16-11-2026").status_code == 400


def test_md_today_shows_the_tv(owner, make_user, session_for, client, md, clock):
    ids, m = setup(owner, make_user, session_for, client, md, clock)
    code = As(client, session_for, ids["M"]).post("/api/kiosks").json()["code"]
    client.post("/api/kiosk/pair", json={"token": code})
    assert m.get("/api/md/today").json()["tv"] == {"status": "online", "label": "Online", "last_seen": "09:00",
                                                   "scans_today": 0}


def test_md_people_and_person_history_with_reasons_and_paper(owner, make_user, session_for, client, md, clock):
    ids, m = setup(owner, make_user, session_for, client, md, clock)
    people = m.get("/api/md/people").json()["people"]
    assert [(p["name"], p["active"]) for p in people] == [
        ("Adaeze Obi", True), ("Bola Ade", True), ("Emeka Okonkwo", True), ("Gone Person", False)]

    a = ids["A"]
    add_scan(owner, a, "in", MON, 8, 23)                 # late, reason waiting
    add_scan(owner, a, "in", date(2026, 11, 12), 8, 5)   # Thu: start 10:00 → on time; claimed clock-out
    add_scan(owner, a, "in", date(2026, 11, 11), 8, 31)  # late, approved
    add_scan(owner, a, "out", date(2026, 11, 11), 17, 5)
    add_scan(owner, a, "in", date(2026, 11, 10), 8, 15)  # late, no reason
    add_scan(owner, a, "out", date(2026, 11, 10), 17, 1)
    with owner.begin() as conn:
        def reason(d, typ, claimed=None, decision=None):
            rid = conn.execute(text("INSERT INTO reasons (user_id, work_date, type, claimed_time, text) "
                                    "VALUES (:u, :d, :t, :c, 'x') RETURNING id"),
                               {"u": a, "d": d, "t": typ, "c": claimed}).scalar_one()
            if decision:
                conn.execute(text("INSERT INTO decisions (reason_id, actor_id, decision) VALUES (:r, :m, :d)"),
                             {"r": rid, "m": ids["M"], "d": decision})
        reason(MON, "late")
        reason(date(2026, 11, 12), "missed_clock_out", lagos(date(2026, 11, 12), 17, 40), "approved")
        reason(date(2026, 11, 11), "late", decision="approved")
        conn.execute(text("INSERT INTO scans (user_id, kind, server_time, work_date, source, entered_by, paper_reason) "
                          "VALUES (:u, 'in', :t, :d, 'paper', :m, 'tv_not_working')"),
                     {"u": a, "t": lagos(FRI, 7, 55), "d": FRI, "m": ids["M"]})

    r = m.get(f"/api/md/people/{a}/history")
    assert r.status_code == 200, r.text
    h = r.json()
    assert h["person"] == {"id": a, "name": "Adaeze Obi", "role": "worker", "active": True, "phone_registered": None}
    notes = {d["date"]: d["note"] for d in h["days"]}
    assert notes["2026-11-16"] == "Late · reason waiting"
    assert notes["2026-11-12"] == "Claimed 17:40 · approved by Emeka"
    assert notes["2026-11-11"] == "Late · approved by Emeka"
    assert notes["2026-11-10"] == "No reason"
    assert notes["2026-11-13"].startswith("No reason · In 07:55 from paper by Emeka")  # paper in, no clock-out
    assert h["summary"]["excused"] == 1 and h["summary"]["late"] == 2
    assert m.get(f"/api/md/people/{md}/history").status_code == 404
    assert m.get(f"/api/md/people/{ids['X']}/history").status_code == 200  # history is kept


def test_privacy_notice_is_public_and_names_the_contact(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "privacy_contact", "Folake Adeyemi (MD), folake@company.test")
    r = client.get("/api/privacy")
    assert r.status_code == 200
    assert r.json()["contact"] == "Folake Adeyemi (MD), folake@company.test"
