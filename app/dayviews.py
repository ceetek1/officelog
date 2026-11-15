"""Loads scans, reasons and decisions from the database and hands them to the pure rules in
``app/rules/day.py``. Nothing here decides anything; it only gathers the facts."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, aliased

from app.config import Settings
from app.models import Decision, Reason, Scan, User
from app.rules.day import DayView, DecisionFact, ReasonFact, ScanFact, day_view
from app.timeutil import local_hhmm


def load_views(
    db: DbSession, settings: Settings, users: list[User], start: date, end: date, now: datetime,
) -> dict[tuple[int, date], DayView]:
    """Day views for every user and every date in [start, end]."""
    tz = settings.tz
    ids = [u.id for u in users]
    if not ids:
        return {}
    entered = aliased(User)
    scans: dict[tuple[int, date], list[ScanFact]] = defaultdict(list)
    for s, by in db.execute(
        select(Scan, entered.name).outerjoin(entered, entered.id == Scan.entered_by)
        .where(Scan.user_id.in_(ids), Scan.work_date >= start, Scan.work_date <= end)
    ):
        scans[(s.user_id, s.work_date)].append(
            ScanFact(kind=s.kind, at=s.server_time.astimezone(tz), source=s.source, entered_by=by))

    reasons = db.scalars(
        select(Reason).where(Reason.user_id.in_(ids), Reason.work_date >= start, Reason.work_date <= end)
    ).all()
    decisions: dict[int, list[DecisionFact]] = defaultdict(list)
    if reasons:
        actor = aliased(User)
        for d, name in db.execute(
            select(Decision, actor.name).join(actor, actor.id == Decision.actor_id)
            .where(Decision.reason_id.in_([r.id for r in reasons]))
        ):
            decisions[d.reason_id].append(DecisionFact(decision=d.decision, at=d.created_at, seq=d.id,
                                                       actor=name, is_override=d.is_override))
    facts: dict[tuple[int, date], list[ReasonFact]] = defaultdict(list)
    for r in reasons:
        facts[(r.user_id, r.work_date)].append(ReasonFact(
            type=r.type, claimed_time=r.claimed_time.astimezone(tz) if r.claimed_time else None,
            decisions=tuple(decisions[r.id])))

    local_now = now.astimezone(tz)
    holidays = settings.holiday_dates
    out = {}
    d = start
    while d <= end:
        day = settings.schedule.for_date(d)
        for u in users:
            out[(u.id, d)] = day_view(d, day, holiday=d in holidays, active=u.active, now=local_now,
                                      scans=scans[(u.id, d)], reasons=facts[(u.id, d)])
        d += timedelta(days=1)
    return out


def view_json(v: DayView, tz) -> dict:
    cin, cout = v.clock_in, v.clock_out
    return {
        "date": v.date.isoformat(),
        "label": f"{v.date:%a} {v.date.day}",
        "working_day": v.working_day,
        "status": v.status,
        "clock_in": None if cin is None else {
            "time": local_hhmm(cin.at, tz), "at": cin.at.isoformat(), "source": cin.source,
            "entered_by": cin.entered_by,
        },
        "clock_out": None if cout is None else {
            "time": local_hhmm(cout.at, tz), "at": cout.at.isoformat(), "source": cout.source,
            "entered_by": cout.entered_by, "approved_by": cout.approved_by,
        },
        "late_minutes": v.late_minutes,
        "late_excused": v.late_excused,
        "absent": v.absent,
        "absent_excused": v.absent_excused,
        "missing_clock_out": v.missing_clock_out,
        "left_early_minutes": v.left_early_minutes,
        "left_early_excused": v.left_early_excused,
        "worked_minutes": v.worked_minutes,
        "not_in_yet": v.not_in_yet,
        "reasons": v.reasons,
    }
