"""Usage numbers (spec §9, §11 step 6 done check): they match a scripted set of test scans, and
20 scans within one minute all succeed."""

import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app import admin
from app.rules.usage import first_try, median, pct
from tests.conftest import register_phone
from tests.test_reasons import As

LAGOS = ZoneInfo("Africa/Lagos")
MON, TUE, WED = date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 18)


def at(d: date, h: int, m: int = 0, s: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, s, tzinfo=LAGOS)


# ---- the pure parts ----

def test_first_try_counts_goals_that_end_in_a_success():
    assert first_try([["ok", "ok"]]) == (2, 2)                    # in and out, first time each
    assert first_try([["stale_code", "ok", "ok"]]) == (1, 2)      # needed a second go to clock in
    assert first_try([["face_id_failed", "stale_code", "ok"]]) == (0, 1)
    assert first_try([["ok", "already_clocked_in"]]) == (1, 2)    # a pointless second scan is a failed try
    assert first_try([["not_logged_in"], ["ok"]]) == (1, 2)
    assert first_try([]) == (0, 0)


def test_median_and_percent():
    assert median([]) is None and median([3]) == 3 and median([1, 9, 2, 4]) == 3
    assert pct(1, 0) is None and pct(10, 13) == 77 and pct(20, 23) == 87 and pct(1, 2) == 50


# ---- the scripted set ----

@pytest.fixture
def scripted(owner, make_user, md, clock):
    """Mon–Wed 16–18 Nov. Five people on Monday; Dayo is deactivated on Tuesday morning."""
    ids = {n: make_user(full, role) for n, full, role in (
        ("A", "Adaeze Obi", "worker"), ("B", "Bola Ade", "worker"), ("C", "Chinedu Eze", "worker"),
        ("M", "Emeka Okonkwo", "manager"), ("D", "Dayo Bello", "worker"))}
    with owner.begin() as conn:
        conn.execute(text("UPDATE users SET created_at = :t"), {"t": at(date(2026, 11, 1), 9)})
        conn.execute(text("UPDATE users SET active = false WHERE id = :d"), {"d": ids["D"]})
        conn.execute(text("INSERT INTO activity_log (actor_id, action, entity, entity_id, created_at) "
                          "VALUES (:m, 'user_deactivate', 'user', :d, :t)"),
                     {"m": ids["M"], "d": str(ids["D"]), "t": at(TUE, 10)})

        def scan(who, kind, d, h, m, source="qr"):
            conn.execute(text(
                "INSERT INTO scans (user_id, kind, server_time, work_date, source, entered_by, paper_reason) "
                "VALUES (:u, :k, :t, :d, :s, :e, :r)"),
                {"u": ids[who] if who else None, "k": kind, "t": at(d, h, m), "d": d, "s": source,
                 "e": ids["M"] if source == "paper" else None,
                 "r": "no_smartphone" if source == "paper" else None})

        def attempt(who, result, d, h, m, ms=None):
            conn.execute(text("INSERT INTO scan_attempts (user_id, result, method, client_ms_to_scan, created_at) "
                              "VALUES (:u, :r, 'qr', :ms, :t)"),
                         {"u": ids[who] if who else None, "r": result, "ms": ms, "t": at(d, h, m)})

        # Monday: C never clocks out; everyone else does. B's first scan was stale; one anonymous try.
        for who, ms in (("A", (4000, 5000)), ("M", (2000, 2000)), ("D", (8000, 9000))):
            scan(who, "in", MON, 7, 55); scan(who, "out", MON, 17, 5)
            attempt(who, "ok", MON, 7, 55, ms[0]); attempt(who, "ok", MON, 17, 5, ms[1])
        scan("B", "in", MON, 8, 3); scan("B", "out", MON, 17, 2)
        attempt("B", "stale_code", MON, 8, 2); attempt("B", "ok", MON, 8, 3, 6000); attempt("B", "ok", MON, 17, 2, 7000)
        scan("C", "in", MON, 8, 0); attempt("C", "ok", MON, 8, 0, 3000)
        attempt(None, "not_logged_in", MON, 8, 1)
        # Tuesday: B's clock-in is from paper; the manager doesn't come; C's Face ID failed once.
        scan("A", "in", TUE, 7, 58); scan("A", "out", TUE, 17, 0)
        attempt("A", "ok", TUE, 7, 58, 1000); attempt("A", "ok", TUE, 17, 0, 1000)
        scan("B", "in", TUE, 8, 0, source="paper"); scan("B", "out", TUE, 17, 1); attempt("B", "ok", TUE, 17, 1, 1000)
        scan("C", "in", TUE, 8, 5); scan("C", "out", TUE, 17, 3)
        attempt("C", "face_id_failed", TUE, 8, 4); attempt("C", "ok", TUE, 8, 5, 1000); attempt("C", "ok", TUE, 17, 3, 1000)
        # Wednesday: everyone in and out, first time.
        for who in ("A", "B", "C", "M"):
            scan(who, "in", WED, 7, 50); scan(who, "out", WED, 17, 0)
            attempt(who, "ok", WED, 7, 50, 3000); attempt(who, "ok", WED, 17, 0, 3000)

        def reason(who, typ, d, created, decision=None, by=None):
            rid = conn.execute(text("INSERT INTO reasons (user_id, work_date, type, text, created_at, updated_at) "
                                    "VALUES (:u, :d, :t, 'x', :c, :c) RETURNING id"),
                               {"u": ids[who], "d": d, "t": typ, "c": created}).scalar_one()
            if decision:
                conn.execute(text("INSERT INTO decisions (reason_id, actor_id, decision) VALUES (:r, :a, :d)"),
                             {"r": rid, "a": by, "d": decision})

        reason("B", "late", MON, at(MON, 12), "approved", ids["M"])
        reason("M", "absent", TUE, at(TUE, 9), "rejected", md)
        reason("A", "late", WED, at(WED, 8))
    clock.set(at(WED, 20))
    return ids


EXPECTED_DAYS = [
    # active, both, both %, first try, tries, first %, median ms, failed, no clock-out, reasons, paper
    ("Mon 16 Nov", 5, 4, 80, 8, 10, 80, 5000, 2, 1, 1, 0),
    ("Tue 17 Nov", 4, 2, 50, 4, 5, 80, 1000, 1, 0, 1, 1),
    ("Wed 18 Nov", 4, 4, 100, 8, 8, 100, 3000, 0, 0, 1, 0),
]


def test_usage_numbers_match_the_scripted_scans(scripted, client, session_for, md):
    r = As(client, session_for, md).get("/api/usage?from=2026-11-16&to=2026-11-18")
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["working_days"] == 3 and u["label"] == "16–18 Nov"
    got = [(d["label"], d["active"], d["both"], d["both_pct"], d["first_try"], d["tries"], d["first_try_pct"],
            d["tap_to_receipt_ms"], d["failed"], d["missing_clock_out"], d["reasons"], d["paper"]) for d in u["days"]]
    assert got == EXPECTED_DAYS
    t = u["totals"]
    assert (t["active"], t["both"], t["both_pct"]) == (13, 10, 77)
    assert (t["first_try"], t["tries"], t["first_try_pct"]) == (20, 23, 87)
    assert t["tap_to_receipt_ms"] == 3000
    assert (t["failed"], t["missing_clock_out"], t["reasons"], t["paper"]) == (3, 1, 3, 1)
    assert (t["reasons_approved"], t["reasons_rejected"], t["reasons_waiting"]) == (1, 1, 1)
    assert u["failures"] == [
        {"code": "face_id_failed", "label": "Face ID didn't work", "count": 1},
        {"code": "not_logged_in", "label": "Not signed in", "count": 1},
        {"code": "stale_code", "label": "Code too old", "count": 1},
    ]


def test_usage_command_prints_the_same_numbers(scripted, clock, capsys):
    admin.usage("2026-11-16", "2026-11-18", now=clock.now())
    out = capsys.readouterr().out
    assert "Usage 2026-11-16 to 2026-11-18 (3 working days)" in out
    lines = {ln.split("  ")[0].strip(): ln.split() for ln in out.splitlines() if ln[:3] in ("Mon", "Tue", "Wed", "Tot")}
    assert lines["Mon 16 Nov"][3:] == ["5", "80%", "80%", "5.0", "s", "2", "1", "1", "0"]
    assert lines["Tue 17 Nov"][3:] == ["4", "50%", "80%", "1.0", "s", "1", "0", "1", "1"]
    assert lines["Total"][1:] == ["13", "77%", "87%", "3.0", "s", "3", "1", "3", "1"]
    assert "Both scans: 10 of 13 person-days. First try: 20 of 23." in out
    assert "Reasons: 3 sent, 1 approved, 1 rejected, 1 waiting." in out
    assert "Code too old: 1" in out


def test_days_off_and_future_days_are_left_out(scripted, client, session_for, md):
    """Saturday is a working day in the schedule (decision D5); Sunday isn't; the 19th is tomorrow."""
    m = As(client, session_for, md)
    u = m.get("/api/usage?from=2026-11-14&to=2026-11-30").json()
    assert [d["label"] for d in u["days"]] == ["Sat 14 Nov", "Mon 16 Nov", "Tue 17 Nov", "Wed 18 Nov"]
    assert u["to"] == "2026-11-18"
    assert m.get("/api/usage?from=2026-11-19&to=2026-11-30").json()["detail"]["code"] == "bad_range"
    assert m.get("/api/usage?from=2026-01-01&to=2026-11-18").status_code == 400  # over 93 days
    assert m.get("/api/usage?from=nope").status_code == 400


def test_holidays_are_not_working_days(owner, make_user, md, clock, client, session_for):
    clock.set(at(date(2026, 12, 28), 12))
    u = As(client, session_for, md).get("/api/usage?from=2026-12-24&to=2026-12-26").json()
    assert [d["date"] for d in u["days"]] == ["2026-12-24", "2026-12-26"]  # 25th is a holiday in the tests


# ---- 20 scans within one minute ----

def test_twenty_scans_within_one_minute_all_succeed(client, make_user, invite_for, clock, session_for, md):
    """Spec §11 step 6: twenty people clock in within the same minute; every one succeeds, quickly."""
    from tests.test_clock import finish, start

    clock.set(at(MON, 7, 59, 0))
    phones = []
    for i in range(20):
        uid = make_user(f"Worker {i:02d}", "worker")
        reg, phone = register_phone(client, invite_for(uid))
        assert reg.status_code == 200, reg.text
        phones.append((reg.cookies["att_session"], reg.json()["csrf_token"], phone))
        client.cookies.delete("att_session")

    began = time.monotonic()
    for i, (cookie, csrf, phone) in enumerate(phones):
        clock.set(at(MON, 8, 0, 0) + timedelta(seconds=i * 2.9))  # 08:00:00 … 08:00:55
        client.cookies.delete("att_session")
        client.cookies.set("att_session", cookie)
        st = start(client, csrf, "in", clock=clock)
        assert st.status_code == 200, (i, st.text)
        r = finish(client, csrf, st, phone, client_ms=1800 + i)
        assert r.status_code == 200, (i, r.text)
        assert r.json()["kind"] == "in" and r.json()["time"] == "08:00" and r.json()["late_minutes"] is None
    took = time.monotonic() - began
    assert took < 60, f"20 scans took {took:.1f} s"

    clock.set(at(MON, 9, 0))
    u = As(client, session_for, md).get("/api/usage?from=2026-11-16&to=2026-11-16").json()
    day = u["days"][0]
    assert (day["first_try"], day["tries"], day["failed"]) == (20, 20, 0)
    team = As(client, session_for, md).get("/api/md/today").json()
    assert team["counts"]["on_time"] == 20
