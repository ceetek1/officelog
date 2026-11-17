"""Late boundaries per weekday, extended for Thursday and Saturday, plus left early."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.rules.day import late_minutes, left_early_minutes, worked_minutes
from app.rules.schedule import parse_schedule

LAGOS = ZoneInfo("Africa/Lagos")
S = parse_schedule(None)


def t(day: int, h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 11, day, h, m, s, tzinfo=LAGOS)


@pytest.mark.parametrize("day,label", [(16, "Mon"), (17, "Tue"), (18, "Wed"), (20, "Fri")])
@pytest.mark.parametrize("h,m,s,expected", [
    (8, 0, 0, None), (8, 10, 0, None), (8, 10, 1, 10), (8, 11, 0, 11), (9, 0, 0, 60), (7, 30, 0, None),
])
def test_weekday_late_boundaries(day, label, h, m, s, expected):
    at = t(day, h, m, s)
    assert late_minutes(at, S.for_date(at.date())) == expected


@pytest.mark.parametrize("h,m,s,expected", [
    (10, 0, 0, None), (10, 5, 0, None), (10, 5, 1, 5), (10, 6, 0, 6), (8, 20, 0, None),
])
def test_thursday_late_boundaries(h, m, s, expected):
    """Thursday: start 10:00, grace 5 min."""
    at = t(19, h, m, s)
    assert late_minutes(at, S.for_date(at.date())) == expected


@pytest.mark.parametrize("h,m,s,expected", [
    (8, 5, 0, None), (8, 5, 1, 5), (8, 6, 0, 6),
])
def test_saturday_late_boundaries(h, m, s, expected):
    """Saturday: start 08:00, grace 5 min."""
    at = t(21, h, m, s)
    assert late_minutes(at, S.for_date(at.date())) == expected


def test_sunday_is_never_late():
    at = t(22, 11, 0)
    assert late_minutes(at, S.for_date(at.date())) is None


@pytest.mark.parametrize("day,h,m,s,expected", [
    (16, 17, 0, 0, None), (16, 16, 59, 30, 1), (16, 16, 15, 0, 45), (16, 18, 0, 0, None),
    (19, 15, 0, 0, None), (19, 14, 30, 0, 30),   # Thursday closes 15:00
    (21, 14, 0, 0, 60),                           # Saturday closes 15:00
    (22, 12, 0, 0, None),                         # Sunday
])
def test_left_early(day, h, m, s, expected):
    at = t(day, h, m, s)
    assert left_early_minutes(at, S.for_date(at.date())) == expected


def test_worked_minutes():
    assert worked_minutes(t(16, 8, 4), t(16, 17, 1, 59)) == 8 * 60 + 57
    assert worked_minutes(t(16, 8, 4), None) is None
