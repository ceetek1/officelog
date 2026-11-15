"""Gathers the facts for the usage numbers (spec §9) and hands them to ``app/rules/usage.py``.

Only working days are counted (the schedule's days, minus holidays). A person counts as active on
a day if they had been added by then and weren't deactivated yet (the deactivation time comes from
the activity log). Used by the MD's Usage page and ``python -m app.admin usage``.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.config import Settings
from app.dayviews import load_views
from app.models import ActivityLog, Decision, Reason, Scan, ScanAttempt, User
from app.rules.usage import DayUsage, failure_label, first_try, totals
from app.timeutil import work_date

MAX_DAYS = 93


class RangeError(ValueError):
    pass


def check_range(start: date, end: date, today: date) -> tuple[date, date]:
    if start > end:
        raise RangeError("The start date is after the end date.")
    end = min(end, today)
    if start > end:
        raise RangeError("That range is in the future.")
    if (end - start).days >= MAX_DAYS:
        raise RangeError(f"Pick at most {MAX_DAYS} days.")
    return start, end


def usage_report(db: DbSession, settings: Settings, start: date, end: date, now: datetime) -> dict:
    tz = settings.tz
    start, end = check_range(start, end, work_date(now, tz))
    working = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    working = [d for d in working if settings.schedule.for_date(d) is not None and d not in settings.holiday_dates]

    people = db.scalars(select(User).where(User.role.in_(("worker", "manager")))).all()
    deactivated: dict[int, date] = {}
    for entity_id, at in db.execute(
        select(ActivityLog.entity_id, func.max(ActivityLog.created_at))
        .where(ActivityLog.action == "user_deactivate").group_by(ActivityLog.entity_id)
    ):
        if entity_id and entity_id.isdigit():
            deactivated[int(entity_id)] = work_date(at, tz)

    def active_on(u: User, d: date) -> bool:
        if work_date(u.created_at, tz) > d:
            return False
        if u.active:
            return True
        gone = deactivated.get(u.id)
        return gone is not None and gone > d

    # Local-date window, as UTC instants, for created_at columns.
    lo = datetime.combine(start, datetime.min.time(), tzinfo=tz)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz)

    app_scans: dict[date, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    paper: Counter[date] = Counter()
    for uid, kind, wd, source in db.execute(
        select(Scan.user_id, Scan.kind, Scan.work_date, Scan.source)
        .where(Scan.work_date >= start, Scan.work_date <= end)
    ):
        if source == "paper":
            paper[wd] += 1
        else:
            app_scans[wd][uid].add(kind)

    attempts: dict[date, dict[object, list[str]]] = defaultdict(lambda: defaultdict(list))
    tap: dict[date, list[int]] = defaultdict(list)
    failures: Counter[str] = Counter()
    working_set = set(working)
    anon = 0
    for a in db.scalars(select(ScanAttempt).where(ScanAttempt.created_at >= lo, ScanAttempt.created_at < hi)
                        .order_by(ScanAttempt.created_at, ScanAttempt.id)):
        d = work_date(a.created_at, tz)
        if d not in working_set:
            continue
        key: object = a.user_id
        if key is None:  # nobody signed in: its own failed try
            anon += 1
            key = ("anon", anon)
        attempts[d][key].append(a.result)
        if a.result == "ok":
            if a.client_ms_to_scan is not None:
                tap[d].append(a.client_ms_to_scan)
        else:
            failures[a.result] += 1

    reasons_per_day: Counter[date] = Counter()
    reasons = db.scalars(select(Reason).where(Reason.created_at >= lo, Reason.created_at < hi)).all()
    for r in reasons:
        reasons_per_day[work_date(r.created_at, tz)] += 1
    latest: dict[int, str] = {}
    if reasons:
        for d in db.scalars(select(Decision).where(Decision.reason_id.in_([r.id for r in reasons]))
                            .order_by(Decision.id)):
            latest[d.reason_id] = d.decision
    # Totals count every reason sent in the range, also on days off; the per-day rows show working days.
    decided = Counter(latest.get(r.id, "waiting") for r in reasons)

    views = load_views(db, settings, list(people), start, end, now) if working else {}

    rows = []
    per_day: list[DayUsage] = []
    for d in working:
        du = DayUsage()
        for u in people:
            if not active_on(u, d):
                continue
            du.active += 1
            if app_scans[d].get(u.id, set()) >= {"in", "out"}:
                du.both += 1
            if views[(u.id, d)].missing_clock_out:
                du.missing_out += 1
        du.first_ok, du.goals = first_try(list(attempts[d].values()))
        du.tap_ms = tap[d]
        du.failed = sum(1 for results in attempts[d].values() for r in results if r != "ok")
        du.reasons = reasons_per_day[d]
        du.paper = paper[d]
        per_day.append(du)
        rows.append({"date": d.isoformat(), "label": f"{d:%a} {d.day} {d:%b}", **du.as_dict()})

    return {
        "from": start.isoformat(), "to": end.isoformat(),
        "label": _range_label(start, end),
        "working_days": len(working),
        "totals": {**totals(per_day), "reasons": len(reasons), "reasons_approved": decided["approved"],
                   "reasons_rejected": decided["rejected"], "reasons_waiting": decided["waiting"]},
        "failures": [{"code": c, "label": failure_label(c), "count": n}
                     for c, n in sorted(failures.items(), key=lambda kv: (-kv[1], kv[0]))],
        "days": rows,
    }


def _range_label(a: date, b: date) -> str:
    if a == b:
        return f"{a.day} {a:%b}"
    if (a.year, a.month) == (b.year, b.month):
        return f"{a.day}–{b.day} {b:%b}"
    return f"{a.day} {a:%b} – {b.day} {b:%b}"
