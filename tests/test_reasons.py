"""Reasons, decisions and override."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text


LAGOS = ZoneInfo("Africa/Lagos")
MON = date(2026, 11, 16)


def lagos(d: date, h: int, m: int) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=LAGOS)


def add_scan(owner, uid, kind, d, h, m):
    with owner.begin() as conn:
        conn.execute(text("INSERT INTO scans (user_id, kind, server_time, work_date, source) VALUES (:u,:k,:t,:d,'qr')"),
                     {"u": uid, "k": kind, "t": lagos(d, h, m), "d": d})


class As:
    """A signed-in client for one user."""

    def __init__(self, client, session_for, uid):
        self.client, self.token, self.csrf = client, *session_for(uid)

    def _go(self, method, url, **kw):
        self.client.cookies.delete("att_session")  # a phone sign-in may have set one for another domain
        self.client.cookies.set("att_session", self.token)
        return self.client.request(method, url, headers={"X-CSRF-Token": self.csrf}, **kw)

    def get(self, url):
        return self._go("GET", url)

    def post(self, url, body=None):
        return self._go("POST", url, json=body or {})

    def put(self, url, body=None):
        return self._go("PUT", url, json=body or {})


def people(client, make_user, session_for, md):
    """The manager, two workers and the MD, each with their own signed-in helper."""
    ids = {"manager": make_user("Emeka Okonkwo", "manager"), "worker": make_user("Adaeze Obi", "worker"),
           "worker2": make_user("Bola Ade", "worker"), "md": md}
    return ids, {k: As(client, session_for, v) for k, v in ids.items()}


def late_reason(who: As, d=MON, text_="Danfo broke down at Ojota."):
    return who.post("/api/reasons", {"work_date": d.isoformat(), "type": "late", "text": text_})


def activity(owner):
    with owner.connect() as conn:
        return conn.execute(text("SELECT action, actor_id, before, after FROM activity_log ORDER BY id")).all()


# ---- sending ----

def test_worker_sends_a_late_reason(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 23)
    clock.set(lagos(MON, 9, 0))
    r = late_reason(u["worker"])
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "waiting" and r.json()["detail"] == "23 min"
    mine = u["worker"].get("/api/reasons/mine").json()
    assert [x["type"] for x in mine["reasons"]] == ["late"] and mine["decided_by"] == "your manager"
    assert ("reason_create", ids["worker"]) == activity(owner)[-1][:2]


def test_one_reason_per_type_per_day(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 23)
    clock.set(lagos(MON, 9, 0))
    late_reason(u["worker"])
    assert late_reason(u["worker"]).status_code == 409


def test_reason_must_match_what_happened(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 0)  # on time
    clock.set(lagos(MON, 18, 30))
    assert late_reason(u["worker"]).status_code == 400
    r = u["worker"].post("/api/reasons", {"work_date": MON.isoformat(), "type": "absent", "text": "x"})
    assert r.status_code == 400  # clocked in


def test_reasons_up_to_7_days_later_and_not_in_the_future(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 23)
    clock.set(lagos(MON + timedelta(days=7), 9, 0))
    assert late_reason(u["worker"]).status_code == 200
    clock.set(lagos(MON + timedelta(days=8), 9, 0))
    r = u["worker"].post("/api/reasons", {"work_date": MON.isoformat(), "type": "left_early", "text": "x"})
    assert r.status_code == 400
    r = u["worker"].post("/api/reasons", {"work_date": (MON + timedelta(days=9)).isoformat(), "type": "absent", "text": "x"})
    assert r.status_code == 400


def test_missed_clock_out_needs_a_time_after_clock_in(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 0)
    clock.set(lagos(MON + timedelta(days=1), 9, 0))
    send = lambda t: u["worker"].post("/api/reasons", {"work_date": MON.isoformat(), "type": "missed_clock_out",  # noqa: E731
                                                       "text": "Forgot to scan out.", "claimed_time": t})
    assert send(None).status_code == 400
    assert send("07:30").status_code == 400
    assert send("5pm").status_code == 400
    assert send("17:40").status_code == 200


def test_absent_reason_can_be_sent_ahead_on_the_day(client, make_user, session_for, md, clock):
    ids, u = people(client, make_user, session_for, md)
    clock.set(lagos(MON, 7, 0))
    r = u["worker"].post("/api/reasons", {"work_date": MON.isoformat(), "type": "absent", "text": "Hospital."})
    assert r.status_code == 200


def test_edit_only_while_waiting(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 23)
    clock.set(lagos(MON, 9, 0))
    rid = late_reason(u["worker"]).json()["id"]
    assert u["worker"].put(f"/api/reasons/{rid}", {"text": "Bus broke down."}).status_code == 200
    assert u["worker2"].put(f"/api/reasons/{rid}", {"text": "Hacked."}).status_code == 404  # not theirs
    u["manager"].post(f"/api/reasons/{rid}/decision", {"decision": "approved"})
    assert u["worker"].put(f"/api/reasons/{rid}", {"text": "Changed."}).status_code == 409
    edit = [a for a in activity(owner) if a[0] == "reason_edit"][0]
    assert edit[2]["text"] == "Danfo broke down at Ojota." and edit[3]["text"] == "Bus broke down."


# ---- deciding ----

def test_manager_decides_a_workers_reason(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 23)
    clock.set(lagos(MON, 9, 0))
    rid = late_reason(u["worker"]).json()["id"]
    waiting = u["manager"].get("/api/approvals").json()["waiting"]
    assert [w["id"] for w in waiting] == [rid] and waiting[0]["detail"] == "23 min"
    assert u["manager"].post(f"/api/reasons/{rid}/decision", {"decision": "approved", "note": "OK"}).status_code == 200
    assert u["manager"].post(f"/api/reasons/{rid}/decision", {"decision": "rejected"}).status_code == 409
    today = u["worker"].get("/api/me/today").json()
    assert today["status"] == "excused" and today["late_excused"] and today["late_minutes"] == 23
    assert u["worker"].get("/api/reasons/mine").json()["reasons"][0]["state"] == "approved"


def test_manager_deciding_own_reason_gets_403(client, make_user, session_for, md, owner, clock):
    """Step 4 done check."""
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["manager"], "in", MON, 8, 30)
    clock.set(lagos(MON, 9, 0))
    rid = late_reason(u["manager"]).json()["id"]
    assert u["manager"].post(f"/api/reasons/{rid}/decision", {"decision": "approved"}).status_code == 403
    assert rid not in [w["id"] for w in u["manager"].get("/api/approvals").json()["waiting"]]
    assert u["manager"].get("/api/reasons/mine").json()["decided_by"] == "the MD"
    md_waiting = u["md"].get("/api/approvals").json()["waiting"]
    assert md_waiting[0]["id"] == rid and md_waiting[0]["role"] == "manager"
    assert u["md"].post(f"/api/reasons/{rid}/decision", {"decision": "approved"}).status_code == 200


def test_worker_cannot_decide(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 23)
    clock.set(lagos(MON, 9, 0))
    rid = late_reason(u["worker"]).json()["id"]
    assert u["worker2"].post(f"/api/reasons/{rid}/decision", {"decision": "approved"}).status_code == 403
    assert u["worker"].post(f"/api/reasons/{rid}/decision", {"decision": "approved"}).status_code == 403


def test_md_override_changes_the_result_and_is_logged(client, make_user, session_for, md, owner, clock):
    """Step 4 done check: an override changes the result and appears in the activity log."""
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 23)
    clock.set(lagos(MON, 9, 0))
    rid = late_reason(u["worker"]).json()["id"]
    assert u["md"].post(f"/api/reasons/{rid}/override", {"decision": "approved"}).status_code == 409  # nothing to override
    u["manager"].post(f"/api/reasons/{rid}/decision", {"decision": "rejected"})
    assert u["worker"].get("/api/me/today").json()["status"] == "late"
    clock.advance(minutes=30)
    r = u["md"].post(f"/api/reasons/{rid}/override", {"decision": "approved", "note": "Bridge was closed."})
    assert r.status_code == 200
    assert u["worker"].get("/api/me/today").json()["status"] == "excused"
    mine = u["worker"].get("/api/reasons/mine").json()["reasons"][0]
    assert [d["decision"] for d in mine["decisions"]] == ["rejected", "approved"]  # append-only
    assert mine["decisions"][1]["is_override"] and mine["decisions"][1]["by"] == "Folake Adeyemi"
    over = [a for a in activity(owner) if a[0] == "override"]
    assert len(over) == 1 and over[0][1] == md
    assert over[0][2] == {"state": "rejected"} and over[0][3]["state"] == "approved"
    log = u["md"].get("/api/activity?filter=decisions").json()["entries"]
    assert log[0]["label"] == "Override" and "Rejected → Approved" in log[0]["details"]
    assert "Bridge was closed." in log[0]["details"]


def test_only_md_can_override(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 23)
    clock.set(lagos(MON, 9, 0))
    rid = late_reason(u["worker"]).json()["id"]
    u["manager"].post(f"/api/reasons/{rid}/decision", {"decision": "rejected"})
    assert u["manager"].post(f"/api/reasons/{rid}/override", {"decision": "approved"}).status_code == 403
    assert u["worker"].post(f"/api/reasons/{rid}/override", {"decision": "approved"}).status_code == 403


def test_approved_missed_clock_out_becomes_the_clock_out(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    add_scan(owner, ids["worker"], "in", MON, 8, 0)
    clock.set(lagos(MON + timedelta(days=1), 9, 0))
    rid = u["worker"].post("/api/reasons", {"work_date": MON.isoformat(), "type": "missed_clock_out",
                                             "text": "Forgot.", "claimed_time": "17:40"}).json()["id"]
    u["manager"].post(f"/api/reasons/{rid}/decision", {"decision": "approved"})
    day = next(d for d in u["worker"].get("/api/me/history").json()["days"] if d["date"] == MON.isoformat())
    assert day["clock_out"] == {"time": "17:40", "at": day["clock_out"]["at"], "source": "claimed",
                                "entered_by": None, "approved_by": "Emeka Okonkwo"}
    assert day["worked_minutes"] == 9 * 60 + 40 and not day["missing_clock_out"]


def test_activity_log_is_md_only_and_filterable(client, make_user, session_for, md, owner, clock):
    ids, u = people(client, make_user, session_for, md)
    client.cookies.clear()
    client.post("/api/auth/password-login", json={"email": "folake@company.test", "password": "wrong"})
    assert u["manager"].get("/api/activity").status_code == 403
    assert u["worker"].get("/api/activity").status_code == 403
    failed = u["md"].get("/api/activity?filter=failed").json()["entries"]
    assert failed[0]["label"] == "Failed sign-in" and "folake@company.test" in failed[0]["details"]
    assert u["md"].get("/api/activity?filter=decisions").json()["entries"] == []


def test_activity_log_pages(client, make_user, session_for, md, owner):
    _, u = people(client, make_user, session_for, md)
    with owner.begin() as conn:
        for _ in range(60):
            conn.execute(text("INSERT INTO activity_log (action, entity) VALUES ('kiosk_pair', 'kiosk')"))
    first = u["md"].get("/api/activity").json()
    assert len(first["entries"]) == 50 and first["more"]
    second = u["md"].get(f"/api/activity?before={first['entries'][-1]['id']}").json()
    assert len(second["entries"]) == 10 and not second["more"]

