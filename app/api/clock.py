"""Clock in and out (spec §4.2; decisions D1, D2).

Two calls, so the code's freshness doesn't depend on how fast Face ID is:

1. ``POST /api/clock/start`` with the scanned QR (or typed code). The server checks the code and
   the rules **now**, remembers this moment as the scan time, and returns a Face ID challenge for
   this phone's passkey.
2. ``POST /api/clock/finish`` with the phone's signed answer. The server checks it and records the
   scan with the time from step 1.

Every attempt, including failures, goes into ``scan_attempts`` (spec §9).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app import codes, passkeys
from app.api.kiosk import code_source
from app.auth import CurrentUser, authenticate, forbidden, get_clock
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Device, Scan, ScanAttempt
from app.rules.day import receipt_for
from app.timeutil import local_hhmm, long_date, work_date

router = APIRouter(prefix="/api/clock", tags=["clock"])

CLOCKS_IN = ("worker", "manager")
CONFIRM_WITHIN = timedelta(minutes=5)


def record_attempt(db: DbSession, user_id: int | None, result: str, method: str | None = None,
                   client_ms: int | None = None, now: datetime | None = None) -> None:
    db.add(ScanAttempt(user_id=user_id, result=result, method=method, client_ms_to_scan=client_ms,
                       **({"created_at": now} if now else {})))


def clock_caller(request: Request, db: DbSession = Depends(get_db), clock: Clock = Depends(get_clock)) -> CurrentUser:
    """Like ``require_roles('worker', 'manager')``, but a missing session is counted as a failed
    scan attempt (``not_logged_in``), as the usage numbers need it."""
    now = clock.now()
    try:
        cu = authenticate(request, db, now)
    except HTTPException as exc:
        if exc.status_code == 401:
            record_attempt(db, None, "not_logged_in", now=now)
            db.commit()
        raise
    if cu.role not in CLOCKS_IN:
        raise forbidden()
    return cu


clock_caller.allowed_roles = frozenset(CLOCKS_IN)  # type: ignore[attr-defined]


class Fail(Exception):
    def __init__(self, status: int, code: str, message: str, **extra):
        self.status, self.code, self.message, self.extra = status, code, message, extra


def _device(db: DbSession, cu: CurrentUser) -> Device:
    dev = db.get(Device, cu.session.device_id) if cu.session.device_id else None
    if dev is None or dev.revoked_at is not None or dev.user_id != cu.id:
        raise Fail(403, "phone_not_registered", passkeys.NOT_REGISTERED)
    return dev


def _today_scans(db: DbSession, user_id: int, wd) -> dict[str, Scan]:
    return {s.kind: s for s in db.scalars(select(Scan).where(Scan.user_id == user_id, Scan.work_date == wd))}


def _check_rules(kind: str, scans: dict[str, Scan], now: datetime, confirm: bool, tz) -> None:
    if kind == "in" and "in" in scans:
        t = local_hhmm(scans["in"].server_time, tz)
        raise Fail(409, "already_clocked_in", f"You already clocked in today at {t}.", time=t)
    if kind == "out":
        if "in" not in scans:
            raise Fail(409, "not_clocked_in", "You haven't clocked in today.")
        if "out" in scans:
            t = local_hhmm(scans["out"].server_time, tz)
            raise Fail(409, "already_clocked_out", f"You already clocked out today at {t}.", time=t)
        if now - scans["in"].server_time < CONFIRM_WITHIN and not confirm:
            raise Fail(409, "confirm_needed", "You clocked in less than 5 minutes ago. Clock out anyway?")


class Start(BaseModel):
    kind: Literal["in", "out"]
    method: Literal["qr", "typed"]
    code: str = Field(min_length=1, max_length=40)
    confirm: bool = False


@router.post("/start")
def start(
    body: Start,
    cu: CurrentUser = Depends(clock_caller),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    tz = settings.tz
    try:
        device = _device(db, cu)
        date_of = lambda unix: work_date(datetime.fromtimestamp(unix, tz), tz)  # noqa: E731
        if body.method == "qr":
            window = codes.check_qr(body.code, now.timestamp(), code_source(settings), date_of)
            if window is None:
                if not codes.is_qr_shaped(body.code):
                    raise Fail(400, "not_our_code", "That isn't the attendance code. Point at the code on the TV.")
                raise Fail(400, "stale_code", "That code has changed. Scan the TV again.")
        else:
            window = codes.check_typed(body.code, now.timestamp(), code_source(settings), date_of)
            if window is None:
                raise Fail(400, "stale_code", "That code doesn't match. Type the code the TV shows now.")
        wd = work_date(now, tz)
        _check_rules(body.kind, _today_scans(db, cu.id, wd), now, body.confirm, tz)
    except Fail as f:
        record_attempt(db, cu.id, f.code, body.method, now=now)
        db.commit()
        raise HTTPException(status_code=f.status, detail={"code": f.code, "message": f.message, **f.extra}) from None

    ch = passkeys.new_challenge(db, "clock", now, user_id=cu.id, session_id=cu.session.id, data={
        "kind": body.kind, "method": body.method, "server_time": now.isoformat(),
        "work_date": wd.isoformat(), "window": window,
    })
    options = passkeys.authentication_options(settings, ch, device)
    db.commit()
    return {"challenge_id": ch.id, "options": options}


class Finish(BaseModel):
    challenge_id: int
    credential: dict
    client_ms_to_scan: int | None = Field(default=None, ge=0, le=3_600_000)


@router.post("/finish")
def finish(
    body: Finish,
    request: Request,
    cu: CurrentUser = Depends(clock_caller),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    tz = settings.tz
    method = None
    try:
        try:
            ch = passkeys.take_challenge(db, body.challenge_id, "clock", now, session_id=cu.session.id)
        except passkeys.PasskeyError as err:
            raise Fail(400, err.code, "That took too long. Scan the TV again.") from err
        data = ch.data or {}
        method = data.get("method")
        device = _device(db, cu)
        try:
            passkeys.verify_assertion(settings, ch, device, body.credential)
        except passkeys.PasskeyError as err:
            raise Fail(401, err.code, err.message) from err

        at = datetime.fromisoformat(data["server_time"])
        wd = work_date(at, tz)
        scans = _today_scans(db, cu.id, wd)
        _check_rules(data["kind"], scans, at, True, tz)  # again: another phone tab may have won
        scan = Scan(user_id=cu.id, kind=data["kind"], server_time=at, work_date=wd, source=method,
                    kiosk_window=data.get("window"), ip=request.client.host if request.client else None)
        db.add(scan)
        try:
            with db.begin_nested():
                db.flush()
        except IntegrityError:
            raise Fail(409, f"already_clocked_{data['kind']}", "That was already recorded.") from None
    except Fail as f:
        record_attempt(db, cu.id, f.code, method, body.client_ms_to_scan, now=now)
        db.commit()
        raise HTTPException(status_code=f.status, detail={"code": f.code, "message": f.message, **f.extra}) from None

    record_attempt(db, cu.id, "ok", method, body.client_ms_to_scan, now=now)
    db.commit()

    day = settings.schedule.for_date(wd)
    if wd in settings.holiday_dates:
        day = None
    local = at.astimezone(tz)
    clock_in = scans["in"].server_time.astimezone(tz) if "in" in scans else None
    r = receipt_for(scan.kind, local, clock_in, day)
    return {
        "kind": scan.kind,
        "time": local_hhmm(at, tz),
        "date": long_date(wd),
        "working_day": day is not None,
        "late_minutes": r.late_minutes,
        "left_early_minutes": r.left_early_minutes,
        "worked_minutes": r.worked_minutes,
    }
