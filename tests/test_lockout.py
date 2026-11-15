from datetime import datetime, timedelta, timezone

from app.lockout import locked_until

T0 = datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def test_four_failures_do_not_lock():
    assert locked_until([at(0), at(1), at(2), at(3)], at(4)) is None


def test_five_failures_in_15_minutes_lock_for_15_minutes_from_the_fifth():
    fails = [at(0), at(1), at(2), at(3), at(10)]
    assert locked_until(fails, at(10)) == at(25)
    assert locked_until(fails, at(24.9)) == at(25)
    assert locked_until(fails, at(25)) is None


def test_five_failures_spread_over_more_than_15_minutes_do_not_lock():
    assert locked_until([at(0), at(4), at(8), at(12), at(16)], at(16)) is None
