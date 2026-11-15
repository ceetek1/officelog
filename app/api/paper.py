"""Time from the paper sheet (decision D3): the manager or the MD adds a clock-in and/or clock-out
for a person, and must say why.

It is stored as a new scan with ``source = 'paper'``, who entered it and why. It is never edited
(the app's database role can only add scans), it always goes to the activity log, and it is shown
as "added from paper by <name>". The same rules as scanning apply: one clock-in and one clock-out
per person per day, a clock-out needs a clock-in, and no times in the future. The manager may add
their own paper time (owner's answer, 2026-11-15).
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession, aliased

from app import activity
from app.auth import CurrentUser, get_clock, require_roles
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Scan, User
from app.timeutil import local_hhmm, work_date

router = APIRouter(prefix="/api/paper", tags=["paper"])

ALLOWED = require_roles("manager", "md")
DAYS_BACK = 7  # the paper sheet can be typed in up to a week later (builder's choice B15)

REASON_LABELS = {
    "tv_not_working": "TV not working",
    "no_smartphone": "No smartphone",
    "phone_dead_or_forgotten": "Phone dead or forgotten",
}
PaperReason = Literal["tv_not_working", "no_smartphone", "phone_dead_or_forgotten"]


def _fail(status: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


def _day_label(d: date, today: date) -> str:
    prefix = "Today" if d == today else "Yesterday" if d == today - timedelta(days=1) else f"{d:%a}"
    return f"{prefix}, {d.day} {d:%b}"


def _allowed_day(d: date, today: date) -> None:
    if d > today:
        raise _fail(400, "in_future", "That day hasn't happened yet.")
    if d < today - timedelta(days=DAYS_BACK):
        raise _fail(400, "too_old", f"Paper times can be added up to {DAYS_BACK} days later.")


def _scans_by_user(db: DbSession, ids: list[int], d: date) -> dict[int, dict[str, tuple[Scan, str | None]]]:
    by = aliased(User)
    out: dict[int, dict[str, tuple[Scan, str | None]]] = {}
    if not ids:
        return out
    for s, name in db.execute(select(Scan, by.name).outerjoin(by, by.id == Scan.entered_by)
                              .where(Scan.user_id.in_(ids), Scan.work_date == d)):
        out.setdefault(s.user_id, {})[s.kind] = (s, name)
    return out


@router.get("/day")
def paper_day(
    day: date | None = Query(default=None, alias="date"),
    cu: CurrentUser = Depends(ALLOWED),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Everyone who clocks in, with the times already recorded on that day (for the form)."""
    tz = settings.tz
    today = work_date(clock.now(), tz)
    d = day or today
    _allowed_day(d, today)
    users = db.scalars(select(User).where(User.active.is_(True), User.role.in_(("worker", "manager")))
                       .order_by(User.name)).all()
    scans = _scans_by_user(db, [u.id for u in users], d)

    def t(entry):
        if entry is None:
            return None
        s, name = entry
        return {"time": local_hhmm(s.server_time, tz), "source": s.source, "entered_by": name}

    return {
        "date": d.isoformat(), "label": _day_label(d, today),
        "days": [{"date": (today - timedelta(days=i)).isoformat(),
                  "label": _day_label(today - timedelta(days=i), today)} for i in range(DAYS_BACK + 1)],
        "reasons": [{"value": k, "label": v} for k, v in REASON_LABELS.items()],
        "people": [{"user_id": u.id, "name": u.name, "is_me": u.id == cu.id,
                    "clock_in": t(scans.get(u.id, {}).get("in")),
                    "clock_out": t(scans.get(u.id, {}).get("out"))} for u in users],
    }


HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class PaperTime(BaseModel):
    user_id: int
    work_date: date
    clock_in: str | None = None
    clock_out: str | None = None
    reason: PaperReason


def _at(d: date, hhmm: str | None, tz) -> datetime | None:
    if hhmm is None or hhmm == "":
        return None
    m = HHMM.match(hhmm)
    if not m:
        raise _fail(400, "bad_time", "Type the time as HH:MM, for example 08:05.")
    return datetime.combine(d, time(int(m[1]), int(m[2])), tzinfo=tz)


@router.post("")
def add_paper_time(
    body: PaperTime,
    cu: CurrentUser = Depends(ALLOWED),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    tz = settings.tz
    now = clock.now()
    today = work_date(now, tz)
    d = body.work_date
    _allowed_day(d, today)
    t_in, t_out = _at(d, body.clock_in, tz), _at(d, body.clock_out, tz)
    if t_in is None and t_out is None:
        raise _fail(400, "time_needed", "Add a clock-in or a clock-out time.")
    for t in (t_in, t_out):
        if t is not None and t > now:
            raise _fail(400, "in_future", f"{local_hhmm(t, tz)} hasn't happened yet.")

    person = db.scalars(select(User).where(User.id == body.user_id).with_for_update()).first()
    if person is None or person.role not in ("worker", "manager") or not person.active:
        raise _fail(404, "not_found", "That person isn't in the list.")

    existing = _scans_by_user(db, [person.id], d).get(person.id, {})
    if t_in is not None and "in" in existing:
        hhmm = local_hhmm(existing["in"][0].server_time, tz)
        raise _fail(409, "already_clocked_in", f"{person.name} already clocked in at {hhmm} that day.", time=hhmm)
    if t_out is not None:
        if "out" in existing:
            hhmm = local_hhmm(existing["out"][0].server_time, tz)
            raise _fail(409, "already_clocked_out", f"{person.name} already clocked out at {hhmm} that day.", time=hhmm)
        first = t_in or (existing["in"][0].server_time if "in" in existing else None)
        if first is None:
            raise _fail(409, "not_clocked_in", "Add the clock-in first: a clock-out needs one.")
        if t_out <= first:
            raise _fail(400, "out_before_in", "The clock-out must be after the clock-in.")

    label = REASON_LABELS[body.reason]
    added = []
    for kind, at in (("in", t_in), ("out", t_out)):
        if at is None:
            continue
        scan = Scan(user_id=person.id, kind=kind, server_time=at, work_date=d, source="paper",
                    entered_by=cu.id, paper_reason=body.reason, created_at=now)
        db.add(scan)
        try:
            with db.begin_nested():
                db.flush()
        except IntegrityError:
            db.rollback()
            raise _fail(409, f"already_clocked_{kind}", "That was already recorded. Reload and check.") from None
        activity.log(db, actor_id=cu.id, action="paper_time", entity="scan", entity_id=scan.id,
                     after={"user_id": person.id, "kind": kind, "time": local_hhmm(at, tz),
                            "work_date": d.isoformat(), "reason": body.reason, "reason_label": label})
        added.append({"kind": kind, "time": local_hhmm(at, tz)})
    db.commit()
    return {"user_id": person.id, "name": person.name, "work_date": d.isoformat(), "added": added,
            "reason_label": label, "entered_by": cu.user.name}
