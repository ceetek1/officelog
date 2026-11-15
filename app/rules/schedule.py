"""The working schedule, one entry per weekday (decision D5).

The schedule comes from the ``SCHEDULE_JSON`` environment variable, so it can change with a
restart instead of a rebuild. Format (all seven days must be present; ``null`` means a day off)::

    {
      "mon": {"start": "08:00", "grace": 10, "close": "17:00"},
      "tue": ...,
      "thu": {"start": "10:00", "grace": 10, "close": "17:00", "missing_out_after": 60},
      "sun": null
    }

``grace`` is in minutes. ``missing_out_after`` is how many minutes after ``close`` a day with a
clock-in but no clock-out counts as "missing clock-out" (default 60).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, time

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")  # index == date.weekday()

DEFAULT_MISSING_OUT_AFTER = 60


@dataclass(frozen=True)
class DaySchedule:
    start: time
    grace_minutes: int
    close: time
    missing_out_after_minutes: int = DEFAULT_MISSING_OUT_AFTER


@dataclass(frozen=True)
class WeekSchedule:
    days: tuple[DaySchedule | None, ...]  # 7 entries, Monday first

    def for_date(self, d: date) -> DaySchedule | None:
        return self.days[d.weekday()]

    def to_json(self) -> dict:
        out: dict[str, dict | None] = {}
        for key, day in zip(DAY_KEYS, self.days):
            out[key] = None if day is None else {
                "start": day.start.strftime("%H:%M"),
                "grace": day.grace_minutes,
                "close": day.close.strftime("%H:%M"),
                "missing_out_after": day.missing_out_after_minutes,
            }
        return out


def _weekday(start: str, grace: int, close: str) -> dict:
    return {"start": start, "grace": grace, "close": close}


# Decision D5 defaults. Thursday's grace and close are assumed until the owner confirms.
DEFAULT_SCHEDULE_JSON: dict[str, dict | None] = {
    "mon": _weekday("08:00", 10, "17:00"),
    "tue": _weekday("08:00", 10, "17:00"),
    "wed": _weekday("08:00", 10, "17:00"),
    "thu": _weekday("10:00", 10, "17:00"),
    "fri": _weekday("08:00", 10, "17:00"),
    "sat": _weekday("08:00", 5, "15:00"),
    "sun": None,
}


class ScheduleError(ValueError):
    pass


def _parse_hhmm(value: object, where: str) -> time:
    if not isinstance(value, str):
        raise ScheduleError(f"{where}: expected a time like \"08:00\"")
    try:
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    except ValueError as exc:
        raise ScheduleError(f"{where}: expected a time like \"08:00\", got {value!r}") from exc


def _parse_minutes(value: object, where: str, default: int | None = None) -> int:
    if value is None and default is not None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 600:
        raise ScheduleError(f"{where}: expected whole minutes between 0 and 600")
    return value


def parse_schedule(raw: str | dict | None) -> WeekSchedule:
    """Parse ``SCHEDULE_JSON``. ``None`` or an empty string gives the default schedule."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        data: object = DEFAULT_SCHEDULE_JSON
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ScheduleError(f"SCHEDULE_JSON is not valid JSON: {exc}") from exc
    else:
        data = raw
    if not isinstance(data, dict):
        raise ScheduleError("SCHEDULE_JSON must be an object with keys mon … sun")
    unknown = set(data) - set(DAY_KEYS)
    missing = set(DAY_KEYS) - set(data)
    if unknown:
        raise ScheduleError(f"SCHEDULE_JSON has unknown days: {sorted(unknown)}")
    if missing:
        raise ScheduleError(f"SCHEDULE_JSON is missing days: {sorted(missing)} (use null for a day off)")

    days: list[DaySchedule | None] = []
    for key in DAY_KEYS:
        entry = data[key]
        if entry is None:
            days.append(None)
            continue
        if not isinstance(entry, dict):
            raise ScheduleError(f"{key}: expected an object or null")
        extra = set(entry) - {"start", "grace", "close", "missing_out_after"}
        if extra:
            raise ScheduleError(f"{key}: unknown fields {sorted(extra)}")
        start = _parse_hhmm(entry.get("start"), f"{key}.start")
        close = _parse_hhmm(entry.get("close"), f"{key}.close")
        if close <= start:
            raise ScheduleError(f"{key}: close must be after start")
        days.append(
            DaySchedule(
                start=start,
                grace_minutes=_parse_minutes(entry.get("grace"), f"{key}.grace"),
                close=close,
                missing_out_after_minutes=_parse_minutes(
                    entry.get("missing_out_after"), f"{key}.missing_out_after", DEFAULT_MISSING_OUT_AFTER
                ),
            )
        )
    return WeekSchedule(days=tuple(days))


def parse_holidays(raw: str | None) -> frozenset[date]:
    """Parse ``HOLIDAYS``: comma-separated ISO dates, e.g. ``2026-12-25,2026-12-26``."""
    if not raw or not raw.strip():
        return frozenset()
    out = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(date.fromisoformat(part))
        except ValueError as exc:
            raise ScheduleError(f"HOLIDAYS: {part!r} is not a date like 2026-12-25") from exc
    return frozenset(out)
