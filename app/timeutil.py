"""Turning server time into the company's local date and time (spec §3: work_date)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


def work_date(at: datetime, tz: ZoneInfo) -> date:
    return at.astimezone(tz).date()


def local_hhmm(at: datetime, tz: ZoneInfo) -> str:
    return at.astimezone(tz).strftime("%H:%M")
