"""Time from the paper sheet (decision D3)."""

from datetime import date

import pytest
from sqlalchemy import text

from tests.test_reasons import As, add_scan, lagos

MON = date(2026, 11, 16)


@pytest.fixture
def office(client, make_user, session_for, md, clock):
    ids = {"manager": make_user("Emeka Okonkwo", "manager"), "worker": make_user("Tunde Bakare", "worker"),
           "worker2": make_user("Bola Ade", "worker"), "md": md}
    clock.set(lagos(MON, 12, 0))
    return ids, {k: As(client, session_for, v) for k, v in ids.items()}


def paper(who, uid, d=MON, clock_in=None, clock_out=None, reason="no_smartphone"):
    return who.post("/api/paper", {"user_id": uid, "work_date": d.isoformat(), "clock_in": clock_in,
                                   "clock_out": clock_out, "reason": reason})


def test_manager_adds_a_paper_clock_in_shown_with_who_and_logged(office, owner, client):
    ids, u = office
    r = paper(u["manager"], ids["worker"], clock_in="08:05", reason="tv_not_working")
    assert r.status_code == 200, r.text
    assert r.json()["added"] == [{"kind": "in", "time": "08:05"}]
    with owner.connect() as conn:
        row = conn.execute(text("SELECT kind, source, entered_by, paper_reason, work_date FROM scans")).one()
        log = conn.execute(text("SELECT action, actor_id, entity, after FROM activity_log")).one()
    assert tuple(row) == ("in", "paper", ids["manager"], "tv_not_working", MON)
    assert log[:3] == ("paper_time", ids["manager"], "scan")
    assert log[3] == {"user_id": ids["worker"], "kind": "in", "time": "08:05", "work_date": "2026-11-16",
                      "reason": "tv_not_working", "reason_label": "TV not working"}
    # Shown as "added from paper by <name>" on Team today.
    team = u["manager"].get("/api/team/today").json()["people"]
    me = next(p for p in team if p["user_id"] == ids["worker"])
    assert me["clock_in"] == {"time": "08:05", "at": "2026-11-16T08:05:00+01:00", "source": "paper",
                              "entered_by": "Emeka Okonkwo"}
    entries = u["md"].get("/api/activity?filter=paper").json()["entries"]
    assert entries[0]["details"] == "Tunde Bakare · Clock-in 08:05 · 16 Nov · TV not working"


def test_in_and_out_together_and_the_day_counts_it(office):
    ids, u = office
    r = paper(u["manager"], ids["worker"], clock_in="07:58", clock_out="11:30", reason="phone_dead_or_forgotten")
    assert r.status_code == 200 and [a["kind"] for a in r.json()["added"]] == ["in", "out"]
    day = next(p for p in u["manager"].get("/api/team/today").json()["people"] if p["user_id"] == ids["worker"])
    assert day["status"] == "on_time" and day["worked_minutes"] == 212


def test_same_rules_as_scanning(office, owner):
    ids, u = office
    m = u["manager"]
    add_scan(owner, ids["worker"], "in", MON, 8, 2)
    r = paper(m, ids["worker"], clock_in="08:00")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_clocked_in"
    assert r.json()["detail"]["time"] == "08:02"
    r = paper(m, ids["worker2"], clock_out="11:00")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_clocked_in"
    r = paper(m, ids["worker"], clock_out="08:01")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "out_before_in"
    r = paper(m, ids["worker2"], clock_in="12:01")  # it's 12:00
    assert r.status_code == 400 and r.json()["detail"]["code"] == "in_future"
    r = paper(m, ids["worker2"], d=date(2026, 11, 17), clock_in="08:00")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "in_future"
    r = paper(m, ids["worker2"], d=date(2026, 11, 8), clock_in="08:00")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "too_old"
    assert paper(m, ids["worker2"]).json()["detail"]["code"] == "time_needed"
    assert paper(m, ids["worker2"], clock_in="8am").json()["detail"]["code"] == "bad_time"
    assert paper(m, ids["worker2"], clock_in="08:00", reason="other").status_code == 422
    # A clock-out for a scanned clock-in is fine.
    assert paper(m, ids["worker"], clock_out="11:45").status_code == 200
    r = paper(m, ids["worker"], clock_out="11:50")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_clocked_out"
    with owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM scans")).scalar_one() == 2


def test_a_scan_after_a_paper_clock_in_is_refused(office, client, registered, clock):
    from tests.test_clock import start

    uid, _, csrf = registered("Chinedu Eze")
    worker_cookie = client.cookies.get("att_session")
    _, u = office
    assert paper(u["manager"], uid, clock_in="08:30").status_code == 200
    client.cookies.delete("att_session")
    client.cookies.set("att_session", worker_cookie)
    r = start(client, csrf, "in", clock=clock)
    assert r.status_code == 409 and r.json()["detail"] == {
        "code": "already_clocked_in", "message": "You already clocked in today at 08:30.", "time": "08:30"}


def test_last_week_is_allowed(office):
    ids, u = office
    assert paper(u["manager"], ids["worker"], d=date(2026, 11, 9), clock_in="08:00").status_code == 200


def test_md_may_add_and_the_manager_may_add_their_own(office, owner):
    ids, u = office
    assert paper(u["md"], ids["worker"], clock_in="08:00").status_code == 200
    assert paper(u["manager"], ids["manager"], clock_in="08:10").status_code == 200
    with owner.connect() as conn:
        rows = conn.execute(text("SELECT user_id, entered_by FROM scans ORDER BY id")).all()
    assert rows == [(ids["worker"], ids["md"]), (ids["manager"], ids["manager"])]


def test_workers_cant_and_nobody_adds_for_the_md_or_a_deactivated_person(office, make_user):
    ids, u = office
    r = paper(u["worker"], ids["worker"], clock_in="08:00")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"
    assert paper(u["manager"], ids["md"], clock_in="08:00").status_code == 404
    gone = make_user("Yusuf Garba", "worker", active=False)
    assert paper(u["manager"], gone, clock_in="08:00").status_code == 404


def test_paper_day_lists_people_with_their_recorded_times(office, owner):
    ids, u = office
    add_scan(owner, ids["worker"], "in", MON, 8, 2)
    paper(u["manager"], ids["worker2"], clock_in="08:15")
    r = u["manager"].get("/api/paper/day")
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "Today, 16 Nov" and len(body["days"]) == 8
    assert body["days"][1]["label"] == "Yesterday, 15 Nov"
    people = {p["name"]: p for p in body["people"]}
    assert set(people) == {"Emeka Okonkwo", "Tunde Bakare", "Bola Ade"}
    assert people["Tunde Bakare"]["clock_in"] == {"time": "08:02", "source": "qr", "entered_by": None}
    assert people["Bola Ade"]["clock_in"]["entered_by"] == "Emeka Okonkwo"
    assert people["Emeka Okonkwo"]["is_me"] is True
    assert u["manager"].get("/api/paper/day?date=2026-11-17").status_code == 400


def test_paper_times_cant_be_edited_by_the_app(office, owner):
    """The app's database role can only add scans (decision B1); nothing in the API changes one."""
    from sqlalchemy import create_engine
    from sqlalchemy.exc import ProgrammingError

    from app.config import get_settings

    ids, u = office
    paper(u["manager"], ids["worker"], clock_in="08:05")
    eng = create_engine(get_settings().resolved_app_database_url)
    try:
        with pytest.raises(ProgrammingError), eng.begin() as conn:
            conn.execute(text("UPDATE scans SET server_time = server_time - interval '1 hour'"))
    finally:
        eng.dispose()
