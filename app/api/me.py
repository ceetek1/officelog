"""The signed-in worker's (or manager's) own day. The MD has no clock-in (spec §2)."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth import CurrentUser, get_clock, require_roles
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Scan
from app.rules.day import late_minutes, left_early_minutes, worked_minutes
from app.timeutil import local_hhmm, long_date, work_date

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
    now = clock.now()
    wd = work_date(now, tz)
    holiday = wd in settings.holiday_dates
    day = None if holiday else settings.schedule.for_date(wd)
    scans = {s.kind: s for s in db.scalars(select(Scan).where(Scan.user_id == cu.id, Scan.work_date == wd))}
    t_in = scans["in"].server_time.astimezone(tz) if "in" in scans else None
    t_out = scans["out"].server_time.astimezone(tz) if "out" in scans else None

    def on(t) -> datetime:
        return now.astimezone(tz).replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)

    return {
        "name": cu.user.name,
        "work_date": wd.isoformat(),
        "date": long_date(wd),
        "working_day": day is not None,
        "holiday": holiday,
        "schedule": None if day is None else {
            "start": day.start.strftime("%H:%M"),
            "grace_minutes": day.grace_minutes,
            "on_time_until": (on(day.start) + timedelta(minutes=day.grace_minutes)).strftime("%H:%M"),
            "close": day.close.strftime("%H:%M"),
        },
        "clock_in": None if t_in is None else {
            "time": local_hhmm(t_in, tz), "at": t_in.isoformat(), "source": scans["in"].source,
            "late_minutes": late_minutes(t_in, day),
        },
        "clock_out": None if t_out is None else {
            "time": local_hhmm(t_out, tz), "at": t_out.isoformat(), "source": scans["out"].source,
            "left_early_minutes": left_early_minutes(t_out, day),
        },
        "worked_minutes": worked_minutes(t_in, t_out),
        "server_time": now.isoformat(),
    }
