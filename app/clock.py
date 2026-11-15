"""The only place business logic gets "now" from (spec §3).

Code that needs the current time takes a ``Clock``. Production uses ``SystemClock``;
tests use ``FixedClock`` to simulate any moment.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Current time, timezone-aware, in UTC."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """A clock for tests. It only moves when told to."""

    def __init__(self, at: datetime):
        if at.tzinfo is None:
            raise ValueError("FixedClock needs a timezone-aware datetime")
        self._at = at.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FixedClock needs a timezone-aware datetime")
        self._at = at.astimezone(timezone.utc)

    def advance(self, **kwargs: float) -> None:
        self._at = self._at + timedelta(**kwargs)
