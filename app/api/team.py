"""Team today (spec §10): the manager and the MD see everyone's day."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth import CurrentUser, get_clock, require_roles
from app.clock import Clock
from app.config import Settings, get_settings
from app.dayviews import load_views, view_json
from app.db import get_db
from app.models import User
from app.timeutil import long_date, work_date

router = APIRouter(prefix="/api/team", tags=["team"])


@router.get("/today")
def team_today(
    cu: CurrentUser = Depends(require_roles("manager", "md")),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    return team_day(db, settings, work_date(now, settings.tz), now)


def team_day(db: DbSession, settings: Settings, wd, now) -> dict:
    """Everyone who clocks in, on one day (the manager's Team today, the MD's Today board)."""
    tz = settings.tz
    people = db.scalars(
        select(User).where(User.active.is_(True), User.role.in_(("worker", "manager"))).order_by(User.name)
    ).all()
    views = load_views(db, settings, list(people), wd, wd, now)
    rows = []
    for u in people:
        v = views[(u.id, wd)]
        rows.append({"user_id": u.id, "name": u.name, "role": u.role, **view_json(v, tz)})
    rows.sort(key=lambda r: (r["clock_in"]["at"] if r["clock_in"] else "", r["name"]))
    count = lambda status: sum(1 for r in rows if r["status"] == status)  # noqa: E731
    return {
        "work_date": wd.isoformat(),
        "date": long_date(wd),
        "working_day": settings.schedule.for_date(wd) is not None and wd not in settings.holiday_dates,
        "counts": {s: count(s) for s in ("on_time", "late", "not_in_yet", "absent", "excused", "day_off")},
        "people": rows,
    }
