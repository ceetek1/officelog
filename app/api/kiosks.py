"""Setting up and removing the entrance TV: the manager only. The TV itself pairs through ``POST /api/kiosk/pair`` (app/api/kiosk.py)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app import people
from app.auth import CurrentUser, get_clock, require_roles
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Kiosk, Scan, User
from app.timeutil import local_hhmm, work_date

router = APIRouter(prefix="/api/kiosks", tags=["kiosks"])

MANAGER = require_roles("manager")


def _when(at: datetime | None, now: datetime, tz) -> str | None:
    if at is None:
        return None
    local, today = at.astimezone(tz), now.astimezone(tz).date()
    if local.date() == today:
        return f"{local_hhmm(at, tz)} today"
    return f"{local:%a} {local.day} {local:%b}, {local_hhmm(at, tz)}"


@router.get("")
def list_tvs(
    cu: CurrentUser = Depends(MANAGER),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Paired TVs (Online / Offline) and setup links still waiting to be used."""
    now, tz = clock.now(), settings.tz
    rows = db.execute(
        select(Kiosk, User.name).outerjoin(User, User.id == Kiosk.created_by)
        .where(Kiosk.revoked_at.is_(None))
        .where((Kiosk.paired_at.is_not(None)) | (Kiosk.setup_expires_at > now))
        .order_by(Kiosk.id.desc())
    ).all()
    scans_today = db.scalar(select(func.count(Scan.id)).where(
        Scan.work_date == work_date(now, tz), Scan.source.in_(("qr", "typed")))) or 0
    tvs = []
    for k, by in rows:
        if k.paired_at is None:
            status, label = "waiting", "Waiting for setup"
        elif k.last_seen_at and now - k.last_seen_at <= people.ONLINE_WITHIN:
            status, label = "online", "Online"
        else:
            status, label = "offline", "Offline"
        tvs.append({
            "id": k.id, "status": status, "label": label,
            "set_up": None if k.paired_at is None else
            f"{_when(k.paired_at, now, tz)}{', ' + by.split()[0] if by else ''}",
            "last_seen": _when(k.last_seen_at, now, tz),
            "link_expires": _when(k.setup_expires_at, now, tz) if k.paired_at is None else None,
        })
    return {"tvs": tvs, "scans_today": scans_today}


@router.post("")
def create_tv_link(
    cu: CurrentUser = Depends(MANAGER),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    kiosk, code, link = people.create_tv_link(db, cu.id, now)
    db.commit()
    return {"id": kiosk.id, "code": code, "link": link, "tv_page": f"{settings.base_url}/tv",
            "expires": _when(kiosk.setup_expires_at, now, settings.tz)}


@router.post("/{kiosk_id}/revoke")
def revoke_tv(
    kiosk_id: int,
    cu: CurrentUser = Depends(MANAGER),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> dict:
    try:
        people.revoke_tv(db, kiosk_id, cu.id, clock.now())
    except people.PeopleError as err:
        raise HTTPException(status_code=err.status, detail={"code": err.code, "message": err.message}) from None
    db.commit()
    return {"ok": True}
