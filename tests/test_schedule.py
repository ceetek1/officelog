from datetime import date, time

import pytest

from app.rules.schedule import DEFAULT_SCHEDULE_JSON, ScheduleError, parse_holidays, parse_schedule


def test_default_schedule_matches_decision_d5():
    s = parse_schedule(None)
    mon = s.for_date(date(2026, 11, 16))
    thu = s.for_date(date(2026, 11, 19))
    sat = s.for_date(date(2026, 11, 21))
    assert (mon.start, mon.grace_minutes, mon.close) == (time(8), 10, time(17))
    assert (thu.start, thu.grace_minutes, thu.close) == (time(10), 10, time(17))
    assert (sat.start, sat.grace_minutes, sat.close) == (time(8), 5, time(15))
    assert s.for_date(date(2026, 11, 22)) is None  # Sunday off
    for d in (16, 17, 18, 20):  # Mon Tue Wed Fri
        day = s.for_date(date(2026, 11, d))
        assert (day.start, day.grace_minutes, day.close) == (time(8), 10, time(17))
    assert mon.missing_out_after_minutes == 60


def test_schedule_from_json_string():
    raw = dict(DEFAULT_SCHEDULE_JSON, sat={"start": "09:00", "grace": 5, "close": "14:00", "missing_out_after": 30})
    import json

    s = parse_schedule(json.dumps(raw))
    sat = s.for_date(date(2026, 11, 21))
    assert (sat.start, sat.close, sat.missing_out_after_minutes) == (time(9), time(14), 30)
    assert parse_schedule(s.to_json()) == s


@pytest.mark.parametrize("bad", [
    "not json",
    "[]",
    {k: v for k, v in DEFAULT_SCHEDULE_JSON.items() if k != "sun"},  # a missing day
    dict(DEFAULT_SCHEDULE_JSON, funday=None),
    dict(DEFAULT_SCHEDULE_JSON, mon={"start": "17:00", "grace": 10, "close": "08:00"}),
    dict(DEFAULT_SCHEDULE_JSON, mon={"start": "8am", "grace": 10, "close": "17:00"}),
    dict(DEFAULT_SCHEDULE_JSON, mon={"start": "08:00", "grace": -1, "close": "17:00"}),
    dict(DEFAULT_SCHEDULE_JSON, mon={"start": "08:00", "grace": 10, "close": "17:00", "extra": 1}),
])
def test_bad_schedule_is_rejected(bad):
    with pytest.raises(ScheduleError):
        parse_schedule(bad)


def test_holidays():
    assert parse_holidays("") == frozenset()
    assert parse_holidays("2026-12-25, 2026-12-26,") == {date(2026, 12, 25), date(2026, 12, 26)}
    with pytest.raises(ScheduleError):
        parse_holidays("25/12/2026")
