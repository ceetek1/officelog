"""Failed-login lockout (spec §8): 5 failures within 15 minutes lock that email or device for 15
minutes."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import LoginFailure

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)
LOCK_FOR = timedelta(minutes=15)


def locked_until(failure_times: list[datetime], now: datetime) -> datetime | None:
    """Pure: given failure times, when does the current lock end (or None if not locked)?

    A lock starts at the moment the 5th failure inside any 15-minute window happens, and lasts
    15 minutes from then.
    """
    times = sorted(t for t in failure_times if t <= now)
    lock_end = None
    for i in range(MAX_FAILURES - 1, len(times)):
        if times[i] - times[i - (MAX_FAILURES - 1)] <= WINDOW:
            end = times[i] + LOCK_FOR
            if lock_end is None or end > lock_end:
                lock_end = end
    if lock_end is not None and lock_end > now:
        return lock_end
    return None


def check(db: Session, key: str, now: datetime) -> datetime | None:
    rows = db.scalars(
        select(LoginFailure.created_at).where(
            LoginFailure.key == key, LoginFailure.created_at > now - WINDOW - LOCK_FOR
        )
    ).all()
    return locked_until(list(rows), now)


def record_failure(db: Session, key: str, now: datetime) -> None:
    db.add(LoginFailure(key=key, created_at=now))
    # Keep the table small: anything older than a day can't matter.
    db.execute(delete(LoginFailure).where(LoginFailure.created_at < now - timedelta(days=1)))
