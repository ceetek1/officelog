"""Spec §12: one test walks the whole permission table in §2, row by row and role by role.

Each row names an endpoint that does what the row says. "no" means 403 with code "forbidden" (the
role check). "yes" means the role check lets the caller through: any other answer is fine (for
example "phone not registered" for a test session without a phone). Rows whose endpoints arrive in later steps are listed and
skipped with the step that adds them, so the table stays complete.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from tests.test_reasons import As

LAGOS = ZoneInfo("Africa/Lagos")
MON = date(2026, 11, 16)
W, M, D = "worker", "manager", "md"

# (row of §2, method, path, body, roles allowed)
TABLE = [
    ("Clocks in and out", "POST", "/api/clock/start", {"kind": "in", "method": "typed", "code": "000000"}, {W, M}),
    ("Sees own times and history", "GET", "/api/me/history", None, {W, M}),
    ("Sees everyone's times", "GET", "/api/team/today", None, {M, D}),
    ("Submits reasons for own late / absent / missed clock-out", "POST", "/api/reasons",
     {"work_date": "2026-11-16", "type": "absent", "text": "x"}, {W, M}),
    ("Approves or rejects workers' reasons", "POST", "/api/reasons/{worker_reason}/decision", {"decision": "approved"}, {M, D}),
    ("Approves or rejects the manager's reasons", "POST", "/api/reasons/{manager_reason}/decision", {"decision": "approved"}, {D}),
    ("Overrides any decision", "POST", "/api/reasons/{decided_reason}/override", {"decision": "rejected"}, {D}),
    ("Sees the activity log", "GET", "/api/activity", None, {D}),
    pytest.param("Adds, deactivates workers; resets a lost phone", "POST", "/api/people", {}, {M},
                 marks=pytest.mark.skip(reason="People endpoints arrive in Step 5")),
    pytest.param("Sets up or revokes the entrance kiosk", "POST", "/api/kiosks", {}, {M},
                 marks=pytest.mark.skip(reason="Kiosk setup endpoints arrive in Step 5")),
    pytest.param("Sees the usage numbers", "GET", "/api/usage", None, {D},
                 marks=pytest.mark.skip(reason="Usage arrives in Step 6")),
]


@pytest.fixture
def world(client, make_user, session_for, md, owner, clock):
    """Everyone, plus a waiting worker reason, a waiting manager reason and a decided one."""
    ids = {W: make_user("Adaeze Obi", W), M: make_user("Emeka Okonkwo", M), D: md}
    other = make_user("Bola Ade", W)
    clock.set(datetime(2026, 11, 16, 7, 0, tzinfo=LAGOS))
    reasons = {}
    with owner.begin() as conn:
        for key, uid in (("worker_reason", other), ("manager_reason", ids[M]), ("decided_reason", other)):
            typ = "late" if key != "decided_reason" else "absent"
            day = MON if key != "decided_reason" else date(2026, 11, 13)
            reasons[key] = conn.execute(text(
                "INSERT INTO reasons (user_id, work_date, type, text) VALUES (:u, :d, :t, 'x') RETURNING id"),
                {"u": uid, "d": day, "t": typ}).scalar_one()
        conn.execute(text("INSERT INTO decisions (reason_id, actor_id, decision) VALUES (:r, :a, 'approved')"),
                     {"r": reasons["decided_reason"], "a": ids[M]})
    return {role: As(client, session_for, uid) for role, uid in ids.items()}, reasons


@pytest.mark.parametrize("row,method,path,body,allowed", TABLE)
def test_permission_table(world, row, method, path, body, allowed):
    users, reasons = world
    url = path.format(**reasons)
    for role in (W, M, D):
        r = users[role]._go(method, url, **({"json": body} if body is not None else {}))
        detail = r.json().get("detail") if r.status_code >= 400 else None
        code = detail.get("code") if isinstance(detail, dict) else None
        if role in allowed:
            assert r.status_code != 401 and code != "forbidden", (row, role, r.status_code, r.text)
        else:
            assert r.status_code == 403 and code == "forbidden", (row, role, r.status_code, r.text)


def test_manager_deciding_own_reason_is_403(world):
    """§12: 'the manager decides on own reason → 403'."""
    users, reasons = world
    r = users[M].post(f"/api/reasons/{reasons['manager_reason']}/decision", {"decision": "approved"})
    assert r.status_code == 403


def test_nobody_edits_a_recorded_time():
    """§2 last row: there is no endpoint that changes a scan; the database refuses too
    (see test_db_role.py)."""
    from app.main import ROUTERS

    for router in ROUTERS:
        for route in router.routes:
            if "scan" in route.path:
                assert route.methods <= {"GET"}, route.path
