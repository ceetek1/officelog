"""The activity log, for the MD only (spec §2, §6). Read-only; written by app/activity.py."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth import CurrentUser, get_clock, require_roles
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import ActivityLog, User
from app.rules.reasons import LABELS
from app.timeutil import local_hhmm, work_date

router = APIRouter(prefix="/api/activity", tags=["activity"])

# Filter tabs (Prototype B "MD · Activity log") -> actions.
FILTERS: dict[str, tuple[str, ...]] = {
    "resets": ("device_reset", "device_register", "invite_create"),
    "decisions": ("decision", "override", "reason_create", "reason_edit"),
    "failed": ("login_failed", "login_locked"),
    "people": ("user_add", "user_deactivate", "password_reset"),
    "paper": ("paper_time",),
    "tv": ("kiosk_create", "kiosk_pair", "kiosk_revoke"),
}

# action -> (label, tone)
LABELS_FOR = {
    "login_failed": ("Failed sign-in", "bad"), "login_locked": ("Locked out", "bad"),
    "device_register": ("Phone registered", "wait"), "device_reset": ("Phone reset", "warn"),
    "invite_create": ("Invite created", "wait"), "user_add": ("Person added", "wait"),
    "user_deactivate": ("Person deactivated", "warn"), "password_reset": ("Password reset", "warn"),
    "reason_create": ("Reason sent", "wait"), "reason_edit": ("Reason edited", "wait"),
    "decision": ("Decision", "ok"), "override": ("Override", "excused"),
    "paper_time": ("Time from paper", "warn"),
    "kiosk_create": ("TV link created", "wait"), "kiosk_pair": ("TV paired", "wait"),
    "kiosk_revoke": ("TV removed", "warn"),
}

STATE_WORD = {"approved": "Approved", "rejected": "Rejected", "waiting": "Waiting"}


def _day(iso: str | None) -> str:
    if not iso:
        return ""
    d = datetime.fromisoformat(iso).date() if "T" in iso else datetime.strptime(iso, "%Y-%m-%d").date()
    return f"{d.day} {d:%b}"


def describe(row: ActivityLog, names: dict[int, str]) -> str:
    a, b = row.after or {}, row.before or {}
    who = names.get(a.get("user_id")) if a.get("user_id") else None
    if row.action in ("decision", "override"):
        what = f"{who or 'Someone'} · {LABELS.get(a.get('type'), a.get('type'))} · {_day(a.get('work_date'))}"
        change = f"{STATE_WORD.get(b.get('state'), '')} → {STATE_WORD.get(a.get('state'), '')}"
        note = f" · “{a['note']}”" if a.get("note") else ""
        return f"{what} · {change}{note}"
    if row.action in ("reason_create", "reason_edit"):
        return f"{LABELS.get(a.get('type'), 'Reason')} · {_day(a.get('work_date'))}" if a.get("type") else "Text changed"
    if row.action in ("login_failed", "login_locked"):
        if row.entity == "login":
            return f"Email {row.entity_id}"
        reason = {"phone_not_registered": "Phone not registered", "face_id_failed": "Face ID didn't match"}.get(a.get("reason"), "Phone")
        return f"{names.get(a.get('user_id'), '')} {reason}".strip()
    if row.action == "user_add":
        return f"{a.get('name')} · {a.get('role')}"
    if row.action in ("device_register", "invite_create", "device_reset", "user_deactivate"):
        return names.get(a.get("user_id"), "") or ""
    if row.action == "paper_time":
        kind = {"in": "Clock-in", "out": "Clock-out"}.get(a.get("kind"), "")
        return " · ".join(x for x in (who, f"{kind} {a.get('time', '')}".strip(), _day(a.get("work_date")),
                                      a.get("reason_label")) if x)
    if row.action in ("kiosk_create", "kiosk_pair", "kiosk_revoke"):
        return f"TV {row.entity_id}" if row.entity_id else "TV"
    return ""


def _who(r: ActivityLog, names: dict[int, str]) -> str:
    if r.actor_id:
        return names.get(r.actor_id, "Unknown")
    return "Unknown" if r.action in FILTERS["failed"] else "Admin command"


@router.get("")
def activity_log(
    filter: str = Query(default="all"),
    before: int | None = Query(default=None, description="load entries older than this id"),
    cu: CurrentUser = Depends(require_roles("md")),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    tz = settings.tz
    q = select(ActivityLog).order_by(ActivityLog.id.desc()).limit(51)
    if filter in FILTERS:
        q = q.where(ActivityLog.action.in_(FILTERS[filter]))
    if before is not None:
        q = q.where(ActivityLog.id < before)
    rows = db.scalars(q).all()
    more = len(rows) > 50
    rows = rows[:50]
    ids = {r.actor_id for r in rows if r.actor_id} | {
        (r.after or {}).get("user_id") for r in rows if isinstance((r.after or {}).get("user_id"), int)}
    names = dict(db.execute(select(User.id, User.name).where(User.id.in_(ids))).all()) if ids else {}
    today = work_date(clock.now(), tz)
    out = []
    for r in rows:
        local = r.created_at.astimezone(tz)
        when = f"Today {local_hhmm(local, tz)}" if local.date() == today else f"{local.day} {local:%b} {local_hhmm(local, tz)}"
        label, tone = LABELS_FOR.get(r.action, (r.action, "wait"))
        if r.action in ("decision", "override"):
            state = (r.after or {}).get("state")
            tone = "ok" if state == "approved" else "bad" if r.action == "decision" else "excused"
            if r.action == "decision":
                label = STATE_WORD.get(state, "Decision")
        out.append({"id": r.id, "when": when, "at": r.created_at.isoformat(),
                    "who": _who(r, names),
                    "action": r.action, "label": label, "tone": tone, "details": describe(r, names)})
    return {"entries": out, "more": more}
