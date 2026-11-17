"""The MD's pages: the Today board for any day, history per person, and
the usage numbers. All MD only."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession, aliased

from app import people as people_mod
from app.api.me import month_history
from app.api.team import team_day
from app.auth import CurrentUser, get_clock, require_roles
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Decision, Device, Kiosk, Reason, Scan, User
from app.rules.reasons import LABELS
from app.timeutil import local_hhmm, work_date
from app.usage import RangeError, usage_report

router = APIRouter(prefix="/api", tags=["md"])

MD = require_roles("md")


def _first(name: str | None) -> str:
    return (name or "").split(" ")[0]


def _parse_day(value: str | None, today: date) -> date:
    if not value:
        return today
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_date", "message": "Use a date like 2026-11-16."}) from None
    if d > today:
        raise HTTPException(status_code=400, detail={"code": "in_future", "message": "That day hasn't happened yet."})
    return d


def tv_summary(db: DbSession, now: datetime, tz) -> dict | None:
    """The entrance TV for the MD's Today board: status, last seen, scans today."""
    k = db.scalars(select(Kiosk).where(Kiosk.revoked_at.is_(None), Kiosk.paired_at.is_not(None))
                   .order_by(Kiosk.last_seen_at.desc().nulls_last())).first()
    if k is None:
        return None
    online = k.last_seen_at is not None and now - k.last_seen_at <= people_mod.ONLINE_WITHIN
    scans = db.scalar(select(func.count(Scan.id)).where(
        Scan.work_date == work_date(now, tz), Scan.source.in_(("qr", "typed")))) or 0
    seen = None
    if k.last_seen_at:
        local = k.last_seen_at.astimezone(tz)
        seen = local_hhmm(k.last_seen_at, tz) if local.date() == now.astimezone(tz).date() \
            else f"{local:%a} {local.day} {local:%b}, {local_hhmm(k.last_seen_at, tz)}"
    return {"status": "online" if online else "offline", "label": "Online" if online else "Offline",
            "last_seen": seen, "scans_today": scans}


@router.get("/md/today")
def md_today(
    day: str | None = Query(default=None, alias="date"),
    cu: CurrentUser = Depends(MD),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    today = work_date(now, settings.tz)
    d = _parse_day(day, today)
    board = team_day(db, settings, d, now)
    return {**board, "is_today": d == today, "short_date": f"{d:%a} {d.day} {d:%b}",
            "active_people": len(board["people"]), "tv": tv_summary(db, now, settings.tz)}


@router.get("/md/people")
def md_people(
    cu: CurrentUser = Depends(MD),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    users = db.scalars(select(User).where(User.role.in_(("worker", "manager")))).all()
    phones = dict(db.execute(select(Device.user_id, Device.registered_at).where(Device.revoked_at.is_(None))).all())
    out = [{"id": u.id, "name": u.name, "role": u.role, "active": u.active,
            "phone_registered": _short(phones[u.id], settings.tz) if u.id in phones else None}
           for u in users]
    out.sort(key=lambda p: (not p["active"], p["name"].lower()))
    return {"people": out}


def _short(at: datetime, tz) -> str:
    local = at.astimezone(tz)
    return f"{local.day} {local:%b}"


def _notes(db: DbSession, user: User, start: date, end: date, tz) -> dict[str, list[str]]:
    """'Late · approved by Emeka', 'Claimed 17:40 · approved by Emeka', 'Reason waiting'."""
    actor = aliased(User)
    reasons = db.scalars(select(Reason).where(Reason.user_id == user.id, Reason.work_date >= start,
                                              Reason.work_date <= end)).all()
    latest: dict[int, tuple[str, str]] = {}
    if reasons:
        for dec, name in db.execute(select(Decision, actor.name).join(actor, actor.id == Decision.actor_id)
                                    .where(Decision.reason_id.in_([r.id for r in reasons])).order_by(Decision.id)):
            latest[dec.reason_id] = (dec.decision, name)
    notes: dict[str, list[str]] = {}
    for r in sorted(reasons, key=lambda r: r.id):
        label = LABELS.get(r.type, r.type)
        if r.type == "missed_clock_out" and r.claimed_time:
            label = f"Claimed {local_hhmm(r.claimed_time, tz)}"
        if r.id in latest:
            state, who = latest[r.id]
            text = f"{label} · {state} by {_first(who)}"
        else:
            text = f"{label} · reason waiting"
        notes.setdefault(r.work_date.isoformat(), []).append(text)
    return notes


@router.get("/md/people/{user_id}/history")
def md_person_history(
    user_id: int,
    month: str | None = Query(default=None),
    cu: CurrentUser = Depends(MD),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    user = db.get(User, user_id)
    if user is None or user.role not in ("worker", "manager"):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "That person isn't in the list."})
    tz = settings.tz
    h = month_history(db, settings, user, month, clock.now())
    first = date.fromisoformat(h["month"] + "-01")
    notes = _notes(db, user, first, first + timedelta(days=31), tz)
    for d in h["days"]:
        extra = list(notes.get(d["date"], []))
        for key in ("clock_in", "clock_out"):
            t = d[key]
            if t and t.get("source") == "paper":
                extra.append(f"{'In' if key == 'clock_in' else 'Out'} {t['time']} from paper by {_first(t['entered_by'])}")
        needs = d["late_minutes"] is not None or d["absent"] or d["left_early_minutes"] is not None or d["missing_clock_out"]
        if needs and not notes.get(d["date"]):
            extra.insert(0, "No reason")
        d["note"] = " · ".join(extra)
    device = db.scalars(select(Device).where(Device.user_id == user.id, Device.revoked_at.is_(None))).first()
    return {**h, "person": {
        "id": user.id, "name": user.name, "role": user.role, "active": user.active,
        "phone_registered": _short(device.registered_at, tz) if device else None,
    }}


@router.get("/usage")
def usage(
    start: str | None = Query(default=None, alias="from"),
    end: str | None = Query(default=None, alias="to"),
    cu: CurrentUser = Depends(MD),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    """The usage numbers. Default: the last 14 days up to today."""
    now = clock.now()
    today = work_date(now, settings.tz)
    try:
        b = date.fromisoformat(end) if end else today
        a = date.fromisoformat(start) if start else b - timedelta(days=13)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_date", "message": "Use dates like 2026-11-16."}) from None
    try:
        return usage_report(db, settings, a, b, now)
    except RangeError as err:
        raise HTTPException(status_code=400, detail={"code": "bad_range", "message": str(err)}) from None


# ---- The manager: the MD adds them and can make a new invite ----

def _manager_json(db: DbSession, now: datetime, tz) -> dict | None:
    m = db.scalars(select(User).where(User.role == "manager", User.active.is_(True))).first()
    if m is None:
        return None
    ph = people_mod.phone_status(db, [m], now)[m.id]
    label = {"active": "Phone set up", "invited": "Invite waiting", "expired": "Invite expired"}[ph["status"]]
    if ph["status"] == "expired" and ph["label"] == "No phone":
        label = "No phone yet"
    return {"id": m.id, "name": m.name, "status": ph["status"], "label": label,
            "invite_expires": _expires_label(ph["invite_expires_at"], tz) if ph["invite_expires_at"] else None}


def _expires_label(at: datetime, tz) -> str:
    local = at.astimezone(tz)
    return f"{local:%a} {local.day} {local:%b}, {local:%H:%M}"


def _invite_reply(user: User, link: str, now: datetime, tz) -> dict:
    return {"id": user.id, "name": user.name, "link": link,
            "expires": _expires_label(people_mod.invite_expiry(now), tz)}


def _people_http(err: people_mod.PeopleError) -> HTTPException:
    return HTTPException(status_code=err.status, detail={"code": err.code, "message": err.message})


@router.get("/md/manager")
def md_manager(
    cu: CurrentUser = Depends(MD),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    return {"manager": _manager_json(db, clock.now(), settings.tz)}


class NewManager(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@router.post("/md/manager")
def md_add_manager(
    body: NewManager,
    cu: CurrentUser = Depends(MD),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Add the manager and get their one-time invite (48 h). Refused if there already is one."""
    now = clock.now()
    try:
        user, link = people_mod.add_manager(db, body.name, cu.id, now)
    except people_mod.PeopleError as err:
        raise _people_http(err) from None
    db.commit()
    return _invite_reply(user, link, now, settings.tz)


@router.post("/md/manager/new-invite")
def md_manager_new_invite(
    cu: CurrentUser = Depends(MD),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    """A phone reset for the manager: their phone and sessions stop working, a new invite is made."""
    now = clock.now()
    m = db.scalars(select(User).where(User.role == "manager", User.active.is_(True))).first()
    if m is None:
        raise HTTPException(status_code=404, detail={"code": "no_manager", "message": "There's no manager yet. Add one first."})
    try:
        user, link = people_mod.reset_phone(db, m.id, cu.id, now)
    except people_mod.PeopleError as err:
        raise _people_http(err) from None
    db.commit()
    return _invite_reply(user, link, now, settings.tz)
