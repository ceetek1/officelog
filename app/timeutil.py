"""Turning server time into the company's local date and time (spec §3: work_date)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


def work_date(at: datetime, tz: ZoneInfo) -> date:
    return at.astimezone(tz).date()


def local_hhmm(at: datetime, tz: ZoneInfo) -> str:
    return at.astimezone(tz).strftime("%H:%M")


def long_date(d: date) -> str:
    """'Monday 16 November'"""
    return f"{d:%A} {d.day} {d:%B}"


def short_date(d: date) -> str:
    """'Mon 16 Nov'"""
    return f"{d:%a} {d.day} {d:%b}"


def greeting(at: datetime, tz: ZoneInfo) -> str:
    h = at.astimezone(tz).hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"


def first_name(name: str) -> str:
    return name.strip().split()[0] if name.strip() else name
