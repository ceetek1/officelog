"""Who may send and decide reasons. Pure functions."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.rules.day import DayView

SUBMIT_WITHIN_DAYS = 7
LABELS = {"late": "Late", "absent": "Absent", "left_early": "Left early", "missed_clock_out": "Missed clock-out"}


def why_not_submittable(type_: str, work_date: date, today: date, view: DayView,
                        claimed: datetime | None) -> str | None:
    """None if this reason may be sent; otherwise a sentence saying why not."""
    if work_date > today:
        return "You can't send a reason for a day that hasn't happened yet."
    if work_date < today - timedelta(days=SUBMIT_WITHIN_DAYS):
        return f"Reasons can be sent up to {SUBMIT_WITHIN_DAYS} days later."
    if type_ == "late" and view.late_minutes is None:
        return "You weren't late that day."
    if type_ == "absent":
        if not view.working_day:
            return "That wasn't a working day."
        if view.clock_in is not None:
            return "You clocked in that day."
    if type_ == "left_early" and view.left_early_minutes is None:
        return "You didn't leave early that day."
    if type_ == "missed_clock_out":
        if view.clock_in is None:
            return "You didn't clock in that day."
        if view.clock_out is not None and view.clock_out.source != "claimed":
            return "You clocked out that day."
        if claimed is None:
            return "Say what time you left."
        if claimed.date() != work_date or claimed <= view.clock_in.at:
            return "The time you left must be after your clock-in, on the same day."
    return None


def who_decides(owner_role: str) -> tuple[str, ...]:
    """Workers' reasons: the manager or the MD. The manager's reasons: only the MD."""
    return ("manager", "md") if owner_role == "worker" else ("md",)


def may_decide(actor_id: int, actor_role: str, owner_id: int, owner_role: str) -> bool:
    """Nobody decides on their own reason, whatever their role."""
    return actor_id != owner_id and actor_role in who_decides(owner_role)
