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


# ---------------------------------------------------------------------------------------------
# The full day view (spec §3, §6: calculated, never stored).
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ScanFact:
    kind: str                 # "in" or "out"
    at: datetime              # company-local
    source: str               # "qr", "typed" or "paper"
    entered_by: str | None = None   # name, for paper times (decision D3)


@dataclass(frozen=True)
class DecisionFact:
    decision: str             # "approved" or "rejected"
    at: datetime
    seq: int = 0              # tie-break for equal times (the row id)
    actor: str | None = None
    is_override: bool = False


@dataclass(frozen=True)
class ReasonFact:
    type: str                 # late, absent, missed_clock_out, left_early
    claimed_time: datetime | None = None   # company-local, for missed_clock_out
    decisions: tuple[DecisionFact, ...] = ()


def latest_decision(decisions) -> DecisionFact | None:
    """Decisions are append-only; the newest one counts (spec §4.3)."""
    return max(decisions, key=lambda d: (d.at, d.seq), default=None)


def reason_state(reason: ReasonFact | None) -> str | None:
    """None (no reason), "waiting", "approved" or "rejected"."""
    if reason is None:
        return None
    d = latest_decision(reason.decisions)
    return "waiting" if d is None else d.decision


@dataclass(frozen=True)
class ClockOut:
    at: datetime
    source: str               # "qr", "typed", "paper" or "claimed"
    entered_by: str | None = None
    approved_by: str | None = None


@dataclass(frozen=True)
class DayView:
    date: date
    working_day: bool
    clock_in: ScanFact | None
    clock_out: ClockOut | None
    late_minutes: int | None
    late_excused: bool
    absent: bool
    absent_excused: bool
    missing_clock_out: bool
    left_early_minutes: int | None
    left_early_excused: bool
    worked_minutes: int | None
    not_in_yet: bool          # working day, no clock-in, close time not reached
    reasons: dict             # type -> "waiting" / "approved" / "rejected"

    @property
    def status(self) -> str:
        """One word for lists: absent, excused, late, on_time, not_in_yet, day_off."""
        if self.absent:
            return "excused" if self.absent_excused else "absent"
        if self.late_minutes is not None:
            return "excused" if self.late_excused else "late"
        if self.clock_in is not None:
            return "on_time" if self.working_day else "day_off"
        if self.not_in_yet:
            return "not_in_yet"
        return "day_off" if not self.working_day else "not_in_yet"


def _at_on(d: date, t, tz) -> datetime:
    return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=tz)


def day_view(
    d: date,
    day: DaySchedule | None,
    *,
    holiday: bool,
    active: bool,
    now: datetime,
    scans: list[ScanFact],
    reasons: list[ReasonFact],
) -> DayView:
    """Everything the screens show for one person on one date.

    - ``day`` is that weekday's schedule (``None`` = weekly day off). Holidays and days off are never
      late or absent, but their scans still show.
    - ``active=False`` (deactivated person) is never counted absent.
    - ``now`` is company-local; things that depend on the time of day (absent after close, missing
      clock-out after close + ``missing_out_after``) are only flagged once that time has passed.
    """
    tz = now.tzinfo
    working = day is not None and not holiday
    sched = day if working else None
    by_kind = {s.kind: s for s in scans}
    rs = {r.type: r for r in reasons}
    states = {t: reason_state(r) for t, r in rs.items()}

    cin = by_kind.get("in")
    out_scan = by_kind.get("out")
    cout: ClockOut | None = None
    if out_scan is not None:
        cout = ClockOut(at=out_scan.at, source=out_scan.source, entered_by=out_scan.entered_by)
    elif states.get("missed_clock_out") == "approved" and rs["missed_clock_out"].claimed_time is not None:
        dec = latest_decision(rs["missed_clock_out"].decisions)
        cout = ClockOut(at=rs["missed_clock_out"].claimed_time, source="claimed",
                        approved_by=dec.actor if dec else None)

    late = late_minutes(cin.at, sched) if cin else None
    early = left_early_minutes(cout.at, sched) if cout else None

    close_at = _at_on(d, sched.close, tz) if sched else None
    after_close = close_at is not None and now >= close_at
    absent = bool(working and active and cin is None and after_close)
    missing_out = bool(
        sched and cin is not None and cout is None
        and now >= close_at + timedelta(minutes=sched.missing_out_after_minutes)
    )
    return DayView(
        date=d,
        working_day=working,
        clock_in=cin,
        clock_out=cout,
        late_minutes=late,
        late_excused=late is not None and states.get("late") == "approved",
        absent=absent,
        absent_excused=absent and states.get("absent") == "approved",
        missing_clock_out=missing_out,
        left_early_minutes=early,
        left_early_excused=early is not None and states.get("left_early") == "approved",
        worked_minutes=worked_minutes(cin.at if cin else None, cout.at if cout else None),
        not_in_yet=bool(working and active and cin is None and not after_close),
        reasons={t: s for t, s in states.items() if s is not None},
    )
