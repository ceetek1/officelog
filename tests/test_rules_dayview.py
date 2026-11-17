"""Day rule tests: absent, hours (scanned and claimed), latest decision wins, override flips,
missing clock-out, excused, left early excused. Pure: no database."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.rules.day import DecisionFact, ReasonFact, ScanFact, day_view, latest_decision, reason_state
from app.rules.schedule import parse_schedule

LAGOS = ZoneInfo("Africa/Lagos")
S = parse_schedule(None)
MON, THU, SAT, SUN = date(2026, 11, 16), date(2026, 11, 19), date(2026, 11, 21), date(2026, 11, 22)


def at(d: date, h: int, m: int, s: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, s, tzinfo=LAGOS)


def view(d, now, scans=(), reasons=(), holiday=False, active=True):
    return day_view(d, S.for_date(d), holiday=holiday, active=active, now=now,
                    scans=list(scans), reasons=list(reasons))


def scan(kind, d, h, m, s=0, source="qr"):
    return ScanFact(kind=kind, at=at(d, h, m, s), source=source)


def dec(decision, d, h, m, seq=0, override=False, actor="Emeka"):
    return DecisionFact(decision=decision, at=at(d, h, m), seq=seq, is_override=override, actor=actor)


# ---- Absent ----

def test_absent_on_a_working_day_after_close():
    assert view(MON, at(MON, 17, 0)).absent
    assert view(MON, at(MON, 17, 0)).status == "absent"


def test_not_absent_before_close_but_not_in_yet():
    v = view(MON, at(MON, 16, 59))
    assert not v.absent and v.not_in_yet and v.status == "not_in_yet"


def test_not_absent_on_a_weekend():
    assert not view(SUN, at(SUN, 23, 0)).absent
    assert view(SUN, at(SUN, 23, 0)).status == "day_off"


def test_not_absent_on_a_holiday():
    v = view(MON, at(MON, 23, 0), holiday=True)
    assert not v.absent and not v.working_day


def test_not_absent_when_deactivated():
    assert not view(MON, at(MON, 23, 0), active=False).absent


def test_thursday_and_saturday_absent_after_their_own_close():
    assert not view(THU, at(THU, 14, 59)).absent and view(THU, at(THU, 15, 0)).absent
    assert not view(SAT, at(SAT, 14, 59)).absent and view(SAT, at(SAT, 15, 0)).absent


def test_approved_absence_is_excused_and_still_absent():
    r = ReasonFact("absent", decisions=(dec("approved", MON, 18, 0),))
    v = view(MON, at(MON, 18, 30), reasons=[r])
    assert v.absent and v.absent_excused and v.status == "excused"


def test_weekend_scans_still_show():
    v = view(SUN, at(SUN, 18, 0), scans=[scan("in", SUN, 9, 0), scan("out", SUN, 12, 0)])
    assert v.clock_in and v.worked_minutes == 180 and v.late_minutes is None and v.status == "day_off"


# ---- Hours ----

def test_hours_with_a_scanned_clock_out():
    v = view(MON, at(MON, 18, 0), scans=[scan("in", MON, 8, 4), scan("out", MON, 17, 10)])
    assert v.worked_minutes == 9 * 60 + 6 and v.clock_out.source == "qr"


def test_hours_with_an_approved_claimed_clock_out():
    r = ReasonFact("missed_clock_out", claimed_time=at(MON, 17, 40),
                   decisions=(dec("approved", MON, 19, 0, actor="Emeka Okonkwo"),))
    v = view(MON, at(MON, 20, 0), scans=[scan("in", MON, 8, 0)], reasons=[r])
    assert v.clock_out.source == "claimed" and v.clock_out.approved_by == "Emeka Okonkwo"
    assert v.worked_minutes == 9 * 60 + 40
    assert not v.missing_clock_out


def test_waiting_or_rejected_claim_does_not_count():
    for decisions in ((), (dec("rejected", MON, 19, 0),)):
        r = ReasonFact("missed_clock_out", claimed_time=at(MON, 17, 40), decisions=decisions)
        v = view(MON, at(MON, 20, 0), scans=[scan("in", MON, 8, 0)], reasons=[r])
        assert v.clock_out is None and v.worked_minutes is None and v.missing_clock_out


# ---- Missing clock-out (close + 60 min, confirmed 2026-11-15) ----

def test_missing_clock_out_after_close_plus_60():
    s = [scan("in", MON, 8, 0)]
    assert not view(MON, at(MON, 17, 59), scans=s).missing_clock_out
    assert view(MON, at(MON, 18, 0), scans=s).missing_clock_out
    s = [scan("in", THU, 10, 0)]
    assert not view(THU, at(THU, 15, 59), scans=s).missing_clock_out
    assert view(THU, at(THU, 16, 0), scans=s).missing_clock_out


def test_earlier_days_are_judged_as_finished():
    v = view(MON, at(date(2026, 11, 17), 9, 0), scans=[scan("in", MON, 8, 0)])
    assert v.missing_clock_out


# ---- Decisions ----

def test_latest_decision_wins():
    r = ReasonFact("late", decisions=(dec("approved", MON, 9, 0, seq=1), dec("rejected", MON, 10, 0, seq=2)))
    assert reason_state(r) == "rejected"
    r = ReasonFact("late", decisions=(dec("rejected", MON, 10, 0, seq=2), dec("approved", MON, 9, 0, seq=1)))
    assert reason_state(r) == "rejected"  # order of the list doesn't matter


def test_same_time_decisions_use_row_order():
    a, b = dec("approved", MON, 9, 0, seq=1), dec("rejected", MON, 9, 0, seq=2)
    assert latest_decision([b, a]) is b


def test_md_override_flips_the_result():
    late_in = [scan("in", MON, 8, 23)]
    manager_no = ReasonFact("late", decisions=(dec("rejected", MON, 9, 0, seq=1),))
    v = view(MON, at(MON, 12, 0), scans=late_in, reasons=[manager_no])
    assert v.status == "late" and not v.late_excused
    md_yes = ReasonFact("late", decisions=manager_no.decisions + (dec("approved", MON, 11, 0, seq=2, override=True, actor="Folake"),))
    v = view(MON, at(MON, 12, 0), scans=late_in, reasons=[md_yes])
    assert v.status == "excused" and v.late_excused and v.late_minutes == 23  # minutes stay


def test_waiting_reason_shows_as_waiting():
    v = view(MON, at(MON, 12, 0), scans=[scan("in", MON, 8, 23)], reasons=[ReasonFact("late")])
    assert v.reasons == {"late": "waiting"} and v.status == "late"


# ---- Left early ----

def test_left_early_and_excused():
    s = [scan("in", MON, 8, 0), scan("out", MON, 16, 15)]
    v = view(MON, at(MON, 18, 0), scans=s)
    assert v.left_early_minutes == 45 and not v.left_early_excused
    r = ReasonFact("left_early", decisions=(dec("approved", MON, 17, 0),))
    assert view(MON, at(MON, 18, 0), scans=s, reasons=[r]).left_early_excused


def test_paper_time_keeps_who_entered_it():
    s = [ScanFact("in", at(MON, 8, 5), "paper", entered_by="Emeka Okonkwo")]
    v = view(MON, at(MON, 12, 0), scans=s)
    assert v.clock_in.source == "paper" and v.clock_in.entered_by == "Emeka Okonkwo" and v.status == "on_time"
