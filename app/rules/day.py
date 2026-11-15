"""One person's day: late, left early, hours worked (spec §3, decision D4). Pure functions.

Times are company-local, timezone-aware datetimes. Step 3 adds absent, excused and missing
clock-out here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.rules.schedule import DaySchedule


def _at(day_time, on: datetime) -> datetime:
    return on.replace(hour=day_time.hour, minute=day_time.minute, second=0, microsecond=0)


def late_minutes(clock_in: datetime, day: DaySchedule | None) -> int | None:
    """Minutes late, counted from the start time, or ``None`` when on time or not a working day.

    Start 08:00, grace 10: 08:10:00 is on time; 08:10:01 is 10 min late; 08:11 is 11 min late.
    """
    if day is None:
        return None
    start = _at(day.start, clock_in)
    if clock_in <= start + timedelta(minutes=day.grace_minutes):
        return None
    return int((clock_in - start).total_seconds() // 60)


def left_early_minutes(clock_out: datetime, day: DaySchedule | None) -> int | None:
    """Minutes before the close time, rounded up (16:59:30 is 1 min early), or ``None``."""
    if day is None:
        return None
    close = _at(day.close, clock_out)
    if clock_out >= close:
        return None
    return math.ceil((close - clock_out).total_seconds() / 60)


def worked_minutes(clock_in: datetime | None, clock_out: datetime | None) -> int | None:
    if clock_in is None or clock_out is None or clock_out < clock_in:
        return None
    return int((clock_out - clock_in).total_seconds() // 60)


@dataclass(frozen=True)
class Receipt:
    kind: str
    late_minutes: int | None = None
    left_early_minutes: int | None = None
    worked_minutes: int | None = None


def receipt_for(kind: str, at: datetime, clock_in: datetime | None, day: DaySchedule | None) -> Receipt:
    if kind == "in":
        return Receipt(kind="in", late_minutes=late_minutes(at, day))
    return Receipt(kind="out", left_early_minutes=left_early_minutes(at, day),
                   worked_minutes=worked_minutes(clock_in, at))
