"""The signed-in worker's (or manager's) own days. The MD has no clock-in (spec §2)."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from app.auth import CurrentUser, get_clock, require_roles
from app.clock import Clock
from app.config import Settings, get_settings
from app.dayviews import load_views, view_json
from app.db import get_db
from app.timeutil import long_date, work_date

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
    v = load_views(db, settings, [cu.user], wd, wd, now)[(cu.id, wd)]
    day = settings.schedule.for_date(wd) if v.working_day else None

    def on(t) -> datetime:
        return now.astimezone(tz).replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)

    return {
        **view_json(v, tz),
        "name": cu.user.name,
        "work_date": wd.isoformat(),
        "date": long_date(wd),
        "holiday": wd in settings.holiday_dates,
        "schedule": None if day is None else {
            "start": day.start.strftime("%H:%M"),
            "grace_minutes": day.grace_minutes,
            "on_time_until": (on(day.start) + timedelta(minutes=day.grace_minutes)).strftime("%H:%M"),
            "close": day.close.strftime("%H:%M"),
        },
        "server_time": now.isoformat(),
    }


_MONTH = re.compile(r"^(\d{4})-(\d{2})$")


@router.get("/history")
def history(
    month: str | None = Query(default=None, description="YYYY-MM; default this month"),
    cu: CurrentUser = Depends(require_roles(*CLOCKS_IN)),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    """One month, newest day first: working days, plus any day with a clock-in."""
    tz = settings.tz
    now = clock.now()
    today_d = work_date(now, tz)
    if month is None:
        y, m = today_d.year, today_d.month
    else:
        mm = _MONTH.match(month)
        if not mm or not 1 <= int(mm.group(2)) <= 12:
            raise HTTPException(status_code=400, detail={"code": "bad_month", "message": "Use a month like 2026-11."})
        y, m = int(mm.group(1)), int(mm.group(2))
    first = date(y, m, 1)
    joined = work_date(cu.user.created_at, tz).replace(day=1)
    if first > today_d or first < joined:
        raise HTTPException(status_code=404, detail={"code": "no_month", "message": "Nothing for that month."})
    last = min(date(y, m, monthrange(y, m)[1]), today_d)
    start = max(first, work_date(cu.user.created_at, tz))
    views = load_views(db, settings, [cu.user], start, last, now)
    days = [v for (_, d), v in sorted(views.items(), key=lambda kv: kv[0][1], reverse=True)
            if v.working_day or v.clock_in is not None]
    prev_first = (first - timedelta(days=1)).replace(day=1)
    next_first = (date(y, m, 28) + timedelta(days=4)).replace(day=1)
    return {
        "month": f"{y:04d}-{m:02d}",
        "label": f"{first:%B %Y}",
        "prev": prev_first.strftime("%Y-%m") if prev_first >= joined else None,
        "next": next_first.strftime("%Y-%m") if next_first <= today_d else None,
        "summary": {
            "days_in": sum(1 for v in days if v.clock_in is not None),
            "late": sum(1 for v in days if v.late_minutes is not None and not v.late_excused),
            "left_early": sum(1 for v in days if v.left_early_minutes is not None and not v.left_early_excused),
            "absent": sum(1 for v in days if v.absent and not v.absent_excused),
            "worked_minutes": sum(v.worked_minutes or 0 for v in days),
        },
        "days": [view_json(v, tz) for v in days],
    }
