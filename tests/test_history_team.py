"""History by month and Team today."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text

LAGOS = ZoneInfo("Africa/Lagos")


def lagos(d: date, h: int, m: int) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=LAGOS)


def add_scan(owner, uid, kind, d: date, h, m, source="qr", entered_by=None):
    with owner.begin() as conn:
        conn.execute(text(
            "INSERT INTO scans (user_id, kind, server_time, work_date, source, entered_by, paper_reason) "
            "VALUES (:u, :k, :t, :d, :s, :e, :r)"),
            {"u": uid, "k": kind, "t": lagos(d, h, m), "d": d, "s": source, "e": entered_by,
             "r": "tv_not_working" if source == "paper" else None})


def backdate(owner, uid, d: date):
    with owner.begin() as conn:
        conn.execute(text("UPDATE users SET created_at = :t WHERE id = :u"), {"t": lagos(d, 7, 0), "u": uid})


def sign_in(client, session_for, uid):
    token, _ = session_for(uid)
    client.cookies.set("att_session", token)


def test_history_lists_working_days_newest_first(client, make_user, session_for, owner, clock):
    uid = make_user("Adaeze Obi", "worker")
    backdate(owner, uid, date(2026, 11, 2))
    add_scan(owner, uid, "in", date(2026, 11, 13), 7, 56)    # Fri on time
    add_scan(owner, uid, "out", date(2026, 11, 13), 17, 2)
    add_scan(owner, uid, "in", date(2026, 11, 12), 10, 5)    # Thu: 10:05 is on time (grace 5)
    add_scan(owner, uid, "out", date(2026, 11, 12), 14, 30)  # Thu closes 15:00 → left early 30
    add_scan(owner, uid, "in", date(2026, 11, 10), 8, 15)    # Tue late 15
    add_scan(owner, uid, "in", date(2026, 11, 15), 9, 0)     # Sunday scan still listed
    clock.set(lagos(date(2026, 11, 16), 8, 30))              # Monday, not in yet
    sign_in(client, session_for, uid)
    h = client.get("/api/me/history").json()
    assert h["month"] == "2026-11" and h["label"] == "November 2026"
    assert h["prev"] is None and h["next"] is None
    by_date = {d["date"]: d for d in h["days"]}
    assert [d["date"] for d in h["days"]][:3] == ["2026-11-16", "2026-11-15", "2026-11-14"]
    assert by_date["2026-11-16"]["status"] == "not_in_yet"
    assert by_date["2026-11-15"]["status"] == "day_off" and by_date["2026-11-15"]["clock_in"]["time"] == "09:00"
    assert by_date["2026-11-14"]["status"] == "absent"   # Saturday with no clock-in
    assert by_date["2026-11-13"]["status"] == "on_time" and by_date["2026-11-13"]["worked_minutes"] == 9 * 60 + 6
    assert by_date["2026-11-12"]["status"] == "on_time" and by_date["2026-11-12"]["left_early_minutes"] == 30
    assert by_date["2026-11-10"]["late_minutes"] == 15
    assert by_date["2026-11-10"]["missing_clock_out"] is True
    assert "2026-11-01" not in by_date   # before they joined
    assert h["summary"]["days_in"] == 4 and h["summary"]["late"] == 1 and h["summary"]["left_early"] == 1


def test_history_month_navigation(client, make_user, session_for, owner, clock):
    uid = make_user("Adaeze Obi", "worker")
    backdate(owner, uid, date(2026, 10, 20))
    sign_in(client, session_for, uid)
    assert client.get("/api/me/history").json()["prev"] == "2026-10"
    oct_ = client.get("/api/me/history?month=2026-10").json()
    assert oct_["next"] == "2026-11" and oct_["prev"] is None
    assert client.get("/api/me/history?month=2026-12").status_code == 404
    assert client.get("/api/me/history?month=2026-09").status_code == 404
    assert client.get("/api/me/history?month=11-2026").status_code == 400


def test_history_shows_only_my_own_days(client, make_user, session_for, owner):
    me = make_user("Adaeze Obi", "worker")
    other = make_user("Chinedu Eze", "worker")
    add_scan(owner, other, "in", date(2026, 11, 16), 8, 0)
    sign_in(client, session_for, me)
    today = client.get("/api/me/history").json()["days"][0]
    assert today["clock_in"] is None


def test_paper_time_shows_who_added_it(client, make_user, session_for, owner):
    mgr = make_user("Emeka Okonkwo", "manager")
    uid = make_user("Adaeze Obi", "worker")
    add_scan(owner, uid, "in", date(2026, 11, 16), 8, 5, source="paper", entered_by=mgr)
    sign_in(client, session_for, uid)
    t = client.get("/api/me/today").json()
    assert t["clock_in"]["source"] == "paper" and t["clock_in"]["entered_by"] == "Emeka Okonkwo"


def test_team_today(client, make_user, session_for, owner, clock, md):
    mgr = make_user("Emeka Okonkwo", "manager")
    a = make_user("Adaeze Obi", "worker")
    b = make_user("Bola Ade", "worker")
    make_user("Chinedu Eze", "worker")
    make_user("Gone Person", "worker", active=False)
    add_scan(owner, a, "in", date(2026, 11, 16), 8, 23)
    add_scan(owner, b, "in", date(2026, 11, 16), 7, 52)
    add_scan(owner, mgr, "in", date(2026, 11, 16), 8, 1)
    clock.set(lagos(date(2026, 11, 16), 9, 0))
    for viewer in (mgr, md):
        sign_in(client, session_for, viewer)
        t = client.get("/api/team/today").json()
        names = [p["name"] for p in t["people"]]
        assert "Gone Person" not in names and "Folake Adeyemi" not in names  # no MD, no deactivated
        assert t["counts"]["on_time"] == 2 and t["counts"]["late"] == 1 and t["counts"]["not_in_yet"] == 1
        late = next(p for p in t["people"] if p["name"] == "Adaeze Obi")
        assert late["clock_in"]["time"] == "08:23" and late["late_minutes"] == 23
    clock.set(lagos(date(2026, 11, 16), 17, 0))
    t = client.get("/api/team/today").json()
    assert t["counts"]["absent"] == 1 and t["counts"]["not_in_yet"] == 0


def test_worker_cannot_see_the_team(client, make_user, session_for):
    sign_in(client, session_for, make_user("Adaeze Obi", "worker"))
    assert client.get("/api/team/today").status_code == 403
