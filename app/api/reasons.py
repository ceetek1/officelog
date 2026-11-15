"""Reasons, decisions and the MD's override (spec §4.3; decision D4).

- Workers and the manager send reasons for their own days: late, absent, left early, missed
  clock-out. One per type per day, up to 7 days later, editable only while waiting.
- The manager decides workers' reasons; the MD decides the manager's (and may decide workers').
  Nobody decides their own.
- Decisions are append-only. The MD's override adds a new decision; the newest one counts.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession, aliased

from app import activity
from app.auth import CurrentUser, forbidden, get_clock, require_roles
from app.clock import Clock
from app.config import Settings, get_settings
from app.dayviews import load_views
from app.db import get_db
from app.models import Decision, Reason, User
from app.rules.day import latest_decision, DecisionFact
from app.rules.reasons import LABELS, may_decide, why_not_submittable
from app.timeutil import local_hhmm, work_date

router = APIRouter(prefix="/api", tags=["reasons"])

CLOCKS_IN = ("worker", "manager")
DECIDERS = ("manager", "md")


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _decisions(db: DbSession, reason_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {i: [] for i in reason_ids}
    if not reason_ids:
        return out
    actor = aliased(User)
    rows = db.execute(
        select(Decision, actor.name).join(actor, actor.id == Decision.actor_id)
        .where(Decision.reason_id.in_(reason_ids)).order_by(Decision.created_at, Decision.id)
    ).all()
    for d, name in rows:
        out[d.reason_id].append({"id": d.id, "decision": d.decision, "by": name, "note": d.note,
                                 "is_override": d.is_override, "at": d.created_at.isoformat()})
    return out


def _state(decs: list[dict]) -> str:
    if not decs:
        return "waiting"
    latest = latest_decision([DecisionFact(decision=d["decision"], at=datetime.fromisoformat(d["at"]), seq=d["id"])
                              for d in decs])
    return latest.decision if latest else "waiting"


def _reason_json(r: Reason, owner: User, decs: list[dict], settings: Settings, view=None) -> dict:
    tz = settings.tz
    detail = None
    if view is not None:
        if r.type == "late" and view.late_minutes is not None:
            detail = f"{view.late_minutes} min"
        elif r.type == "left_early" and view.left_early_minutes is not None:
            detail = f"{view.left_early_minutes} min"
    return {
        "id": r.id,
        "user_id": owner.id,
        "name": owner.name,
        "role": owner.role,
        "work_date": r.work_date.isoformat(),
        "day_label": f"{r.work_date:%a} {r.work_date.day} {r.work_date:%b}",
        "type": r.type,
        "type_label": LABELS[r.type],
        "detail": detail,
        "clock_in": local_hhmm(view.clock_in.at, tz) if view is not None and view.clock_in else None,
        "claimed_time": local_hhmm(r.claimed_time, tz) if r.claimed_time else None,
        "text": r.text,
        "state": _state(decs),
        "decisions": decs,
        "editable": not decs,
        "created_at": r.created_at.isoformat(),
    }


def _views_for(db, settings, reasons_with_owner, now):
    if not reasons_with_owner:
        return {}
    users = {o.id: o for _, o in reasons_with_owner}
    dates = [r.work_date for r, _ in reasons_with_owner]
    return load_views(db, settings, list(users.values()), min(dates), max(dates), now)


# ---- Sending reasons (own) ----

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class NewReason(BaseModel):
    work_date: date
    type: Literal["late", "absent", "left_early", "missed_clock_out"]
    text: str = Field(min_length=1, max_length=500)
    claimed_time: str | None = Field(default=None, description="HH:MM, for missed_clock_out")


def _claimed(work_d: date, hhmm: str | None, settings: Settings) -> datetime | None:
    if hhmm is None:
        return None
    m = _HHMM.match(hhmm)
    if not m:
        raise _err(400, "bad_time", "Use a time like 17:30.")
    return datetime.combine(work_d, time(int(m.group(1)), int(m.group(2))), tzinfo=settings.tz)


@router.get("/reasons/mine")
def my_reasons(
    cu: CurrentUser = Depends(require_roles(*CLOCKS_IN)),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    rows = db.scalars(select(Reason).where(Reason.user_id == cu.id).order_by(Reason.work_date.desc(), Reason.id.desc())).all()
    decs = _decisions(db, [r.id for r in rows])
    views = _views_for(db, settings, [(r, cu.user) for r in rows], clock.now())
    return {"reasons": [_reason_json(r, cu.user, decs[r.id], settings, views.get((cu.id, r.work_date))) for r in rows],
            "decided_by": "the MD" if cu.role == "manager" else "your manager"}


@router.post("/reasons")
def send_reason(
    body: NewReason,
    cu: CurrentUser = Depends(require_roles(*CLOCKS_IN)),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    today = work_date(now, settings.tz)
    claimed = _claimed(body.work_date, body.claimed_time, settings) if body.type == "missed_clock_out" else None
    view = load_views(db, settings, [cu.user], body.work_date, body.work_date, now)[(cu.id, body.work_date)]
    why = why_not_submittable(body.type, body.work_date, today, view, claimed)
    if why:
        raise _err(400, "not_allowed", why)
    r = Reason(user_id=cu.id, work_date=body.work_date, type=body.type, claimed_time=claimed,
               text=body.text.strip(), created_at=now, updated_at=now)
    db.add(r)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise _err(409, "already_sent", "You already sent this kind of reason for that day. You can edit it while it's waiting.") from None
    activity.log(db, actor_id=cu.id, action="reason_create", entity="reason", entity_id=r.id,
                 after={"user_id": cu.id, "work_date": r.work_date.isoformat(), "type": r.type, "text": r.text,
                        "claimed_time": body.claimed_time})
    db.commit()
    return _reason_json(r, cu.user, [], settings, view)


class EditReason(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    claimed_time: str | None = None


@router.put("/reasons/{reason_id}")
def edit_reason(
    reason_id: int,
    body: EditReason,
    cu: CurrentUser = Depends(require_roles(*CLOCKS_IN)),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    r = db.scalars(select(Reason).where(Reason.id == reason_id).with_for_update()).first()
    if r is None or r.user_id != cu.id:
        raise _err(404, "not_found", "Reason not found.")
    if db.scalar(select(func.count()).select_from(Decision).where(Decision.reason_id == r.id)):
        raise _err(409, "decided", "This reason has been decided, so it can't be changed.")
    before = {"text": r.text, "claimed_time": local_hhmm(r.claimed_time, settings.tz) if r.claimed_time else None}
    claimed = r.claimed_time
    if r.type == "missed_clock_out":
        claimed = _claimed(r.work_date, body.claimed_time, settings)
        view = load_views(db, settings, [cu.user], r.work_date, r.work_date, now)[(cu.id, r.work_date)]
        today = work_date(now, settings.tz)
        why = why_not_submittable(r.type, r.work_date, max(today, r.work_date), view, claimed)
        if why:
            raise _err(400, "not_allowed", why)
    r.text = body.text.strip()
    r.claimed_time = claimed
    r.updated_at = now
    activity.log(db, actor_id=cu.id, action="reason_edit", entity="reason", entity_id=r.id, before=before,
                 after={"text": r.text, "claimed_time": body.claimed_time if r.type == "missed_clock_out" else None})
    db.commit()
    return {"ok": True}


# ---- Approvals ----

@router.get("/approvals")
def approvals(
    cu: CurrentUser = Depends(require_roles(*DECIDERS)),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Reasons this person may decide. The manager sees workers' reasons; the MD sees everyone's."""
    owner = aliased(User)
    q = select(Reason, owner).join(owner, owner.id == Reason.user_id).where(Reason.user_id != cu.id)
    if cu.role == "manager":
        q = q.where(owner.role == "worker")
    rows = db.execute(q.order_by(Reason.created_at.desc(), Reason.id.desc()).limit(300)).all()
    decs = _decisions(db, [r.id for r, _ in rows])
    views = _views_for(db, settings, rows, clock.now())
    items = [_reason_json(r, o, decs[r.id], settings, views.get((o.id, r.work_date))) for r, o in rows]
    waiting = [i for i in items if i["state"] == "waiting"]
    waiting.sort(key=lambda i: (i["role"] != "manager", i["created_at"]))
    return {"waiting": waiting, "decided": [i for i in items if i["state"] != "waiting"],
            "can_override": cu.role == "md"}


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=500)


def _load_for_decision(db: DbSession, reason_id: int) -> tuple[Reason, User, list[Decision]]:
    row = db.execute(
        select(Reason, User).join(User, User.id == Reason.user_id).where(Reason.id == reason_id)
        .with_for_update(of=Reason)
    ).first()
    if row is None:
        raise _err(404, "not_found", "Reason not found.")
    r, owner = row
    decs = db.scalars(select(Decision).where(Decision.reason_id == r.id).order_by(Decision.created_at, Decision.id)).all()
    return r, owner, list(decs)


def _state_of(decs: list[Decision]) -> str:
    return decs[-1].decision if decs else "waiting"


@router.post("/reasons/{reason_id}/decision")
def decide(
    reason_id: int,
    body: DecisionIn,
    cu: CurrentUser = Depends(require_roles(*DECIDERS)),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> dict:
    r, owner, decs = _load_for_decision(db, reason_id)
    if not may_decide(cu.id, cu.role, owner.id, owner.role):
        raise forbidden()
    if decs:
        raise _err(409, "already_decided", "This reason was already decided." +
                   (" Use Override to change it." if cu.role == "md" else ""))
    d = Decision(reason_id=r.id, actor_id=cu.id, decision=body.decision, note=body.note.strip(),
                 is_override=False, created_at=clock.now())
    db.add(d)
    db.flush()
    activity.log(db, actor_id=cu.id, action="decision", entity="reason", entity_id=r.id,
                 before={"state": "waiting"},
                 after={"state": body.decision, "note": d.note, "user_id": owner.id, "type": r.type,
                        "work_date": r.work_date.isoformat()})
    db.commit()
    return {"ok": True, "state": body.decision}


@router.post("/reasons/{reason_id}/override")
def override(
    reason_id: int,
    body: DecisionIn,
    cu: CurrentUser = Depends(require_roles("md")),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> dict:
    """The MD changes any decision. Adds a new decision row; the old ones stay."""
    r, owner, decs = _load_for_decision(db, reason_id)
    if owner.id == cu.id:
        raise forbidden()
    if not decs:
        raise _err(409, "not_decided", "This reason hasn't been decided yet. Approve or reject it instead.")
    before = _state_of(decs)
    d = Decision(reason_id=r.id, actor_id=cu.id, decision=body.decision, note=body.note.strip(),
                 is_override=True, created_at=clock.now())
    db.add(d)
    db.flush()
    activity.log(db, actor_id=cu.id, action="override", entity="reason", entity_id=r.id,
                 before={"state": before},
                 after={"state": body.decision, "note": d.note, "user_id": owner.id, "type": r.type,
                        "work_date": r.work_date.isoformat()})
    db.commit()
    return {"ok": True, "state": body.decision}

