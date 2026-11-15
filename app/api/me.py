"""The signed-in worker's (or manager's) own day. MD has no clock-in (spec §2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth import CurrentUser, get_clock, require_roles
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Scan
from app.timeutil import local_hhmm, work_date

router = APIRouter(prefix="/api/me", tags=["me"])

CLOCKS_IN = ("worker", "manager")


@router.get("/today")
def today(
    cu: CurrentUser = Depends(require_roles(*CLOCKS_IN)),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    tz = settings.tz
    wd = work_date(clock.now(), tz)
    day = settings.schedule.for_date(wd)
    holiday = wd in settings.holiday_dates
    scans = db.scalars(
        select(Scan).where(Scan.user_id == cu.id, Scan.work_date == wd).order_by(Scan.server_time)
    ).all()
    return {
        "work_date": wd.isoformat(),
        "working_day": day is not None and not holiday,
        "holiday": holiday,
        "schedule": None if day is None else {
            "start": day.start.strftime("%H:%M"),
            "grace_minutes": day.grace_minutes,
            "close": day.close.strftime("%H:%M"),
        },
        "scans": [
            {"kind": s.kind, "time": local_hhmm(s.server_time, tz), "source": s.source}
            for s in scans
        ],
    }
