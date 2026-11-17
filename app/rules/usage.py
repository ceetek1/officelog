"""Usage numbers: pure calculations, no database. ``app/usage.py`` gathers the facts.

- **Both scans:** the share of active people with an app clock-in *and* an app clock-out that day.
  Times from the paper sheet and approved claimed clock-outs don't count: this measures the app.
- **First try:** each person's scan attempts on a day are split into "goals", each ending at a
  successful scan (a last goal may never succeed). A goal is a first-try success when its very
  first attempt succeeded. Attempts with nobody signed in can't be tied to a person, so each is
  its own failed goal.
- **Tap to receipt:** the median of ``client_ms_to_scan`` over successful scans.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FAILURE_LABELS = {
    "stale_code": "Code too old",
    "already_clocked_in": "Already clocked in",
    "already_clocked_out": "Already clocked out",
    "not_clocked_in": "Not clocked in yet",
    "not_logged_in": "Not signed in",
    "phone_not_registered": "Phone not registered",
    "face_id_failed": "Face ID didn't work",
    "challenge_expired": "Took too long",
    "not_our_code": "Not the attendance code",
    "confirm_needed": "Clock-out under 5 min (asked to confirm)",
}


def failure_label(code: str) -> str:
    return FAILURE_LABELS.get(code, code.replace("_", " ").capitalize())


def first_try(attempts_by_person: list[list[str]]) -> tuple[int, int]:
    """(first-try successes, goals). Each inner list is one person's results on one day, in order."""
    ok_first = goals = 0
    for results in attempts_by_person:
        start = True
        for r in results:
            if start:
                goals += 1
                if r == "ok":
                    ok_first += 1
            start = r == "ok"  # the next attempt starts a new goal only after a success
    return ok_first, goals


def median(values: list[int]) -> float | None:
    v = sorted(values)
    if not v:
        return None
    mid = len(v) // 2
    return float(v[mid]) if len(v) % 2 else (v[mid - 1] + v[mid]) / 2


def pct(part: int, whole: int) -> int | None:
    """Whole-number percentage, rounded half up; None when there is nothing to divide by."""
    if not whole:
        return None
    return int((part * 100 + whole // 2) // whole)


@dataclass
class DayUsage:
    active: int = 0
    both: int = 0
    first_ok: int = 0
    goals: int = 0
    tap_ms: list[int] = field(default_factory=list)
    failed: int = 0
    missing_out: int = 0
    reasons: int = 0
    paper: int = 0

    def as_dict(self) -> dict:
        m = median(self.tap_ms)
        return {
            "active": self.active, "both": self.both, "both_pct": pct(self.both, self.active),
            "first_try": self.first_ok, "tries": self.goals, "first_try_pct": pct(self.first_ok, self.goals),
            "tap_to_receipt_ms": None if m is None else round(m),
            "failed": self.failed, "missing_clock_out": self.missing_out, "reasons": self.reasons,
            "paper": self.paper,
        }


def totals(days: list[DayUsage]) -> dict:
    """Pooled over the days (so a busy day weighs more than a quiet one)."""
    t = DayUsage()
    for d in days:
        t.active += d.active
        t.both += d.both
        t.first_ok += d.first_ok
        t.goals += d.goals
        t.tap_ms += d.tap_ms
        t.failed += d.failed
        t.missing_out += d.missing_out
        t.reasons += d.reasons
        t.paper += d.paper
    return t.as_dict()
