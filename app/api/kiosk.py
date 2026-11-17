"""The entrance TV.

The TV is paired once with a single-use setup link and then keeps a kiosk token in an httpOnly
cookie. It polls ``GET /api/kiosk/code`` every second; the server makes the codes, so the TV holds
no secret.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import activity, codes
from app.auth import get_clock
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Kiosk, Scan, User
from app.people import normalize_tv_code
from app.security import new_token, token_hash
from app.timeutil import first_name, greeting, local_hhmm, short_date, work_date

router = APIRouter(prefix="/api/kiosk", tags=["kiosk"])

KIOSK_COOKIE = "att_kiosk"
KIOSK_COOKIE_AGE = 400 * 24 * 3600  # browsers cap cookies at 400 days; refreshed on every poll
RECENT = 5


def code_source(settings: Settings) -> codes.SecretSource:
    """Where code secrets come from. Swap this for per-kiosk secrets in a future offline mode."""
    return codes.MasterSecretSource(settings.master_secret.encode())


def _set_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(KIOSK_COOKIE, token, max_age=KIOSK_COOKIE_AGE, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/")


class Pair(BaseModel):
    token: str = Field(min_length=1, max_length=200)


@router.post("/pair")
def pair(
    body: Pair, response: Response, db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock), settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    # The manager's screen shows a short code to type on the TV ("ABCDE-FGHJK"); older links
    # from the admin command carry a long token. Both are single use.
    hashes = {token_hash(body.token), token_hash(normalize_tv_code(body.token))}
    kiosk = db.scalars(
        select(Kiosk).where(Kiosk.setup_token_hash.in_(hashes)).with_for_update()
    ).first()
    if kiosk is None or kiosk.paired_at is not None or kiosk.revoked_at is not None or kiosk.setup_expires_at <= now:
        raise HTTPException(status_code=410, detail={
            "code": "pair_invalid",
            "message": "That TV setup code has expired, was already used, or is mistyped. Ask the manager for a new one."})
    token = new_token()
    kiosk.token_hash = token_hash(token)
    kiosk.paired_at = now
    kiosk.last_seen_at = now
    activity.log(db, actor_id=None, action="kiosk_pair", entity="kiosk", entity_id=kiosk.id)
    db.commit()
    _set_cookie(response, token, settings)
    return {"ok": True}


def current_kiosk(request: Request, db: DbSession, now: datetime) -> tuple[Kiosk, str]:
    token = request.cookies.get(KIOSK_COOKIE)
    kiosk = None
    if token:
        kiosk = db.scalars(select(Kiosk).where(Kiosk.token_hash == token_hash(token))).first()
    if kiosk is None or kiosk.revoked_at is not None:
        raise HTTPException(status_code=401, detail={
            "code": "kiosk_not_paired", "message": "This TV isn't set up. Ask the manager for the TV setup link."})
    return kiosk, token


@router.get("/code")
def code(
    request: Request, response: Response, db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock), settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    kiosk, token = current_kiosk(request, db, now)
    if kiosk.last_seen_at is None or now - kiosk.last_seen_at > timedelta(minutes=1):
        kiosk.last_seen_at = now
        db.commit()
    _set_cookie(response, token, settings)

    tz = settings.tz
    unix = now.timestamp()
    wd = work_date(now, tz)
    src = code_source(settings)
    [secret] = list(src.secrets_for(wd))[:1]
    qw, tw = codes.qr_window(unix), codes.typed_window(unix)

    rows = db.execute(
        select(Scan.id, Scan.kind, Scan.server_time, User.name)
        .join(User, User.id == Scan.user_id)
        .where(Scan.work_date == wd, Scan.source.in_(("qr", "typed")))
        .order_by(Scan.server_time.desc(), Scan.id.desc())
        .limit(RECENT)
    ).all()
    # First name and time only. Never "late" on the TV.
    recent = [{"id": i, "name": first_name(n), "time": local_hhmm(t, tz), "kind": k} for i, k, t, n in rows]

    return {
        "qr": codes.qr_content(secret, qw),
        "qr_ms_left": int(((qw + 1) * codes.QR_STEP - unix) * 1000),
        "typed": codes.typed_code(secret, tw),
        "typed_ms_left": int(((tw + 1) * codes.TYPED_STEP - unix) * 1000),
        "typed_step_ms": codes.TYPED_STEP * 1000,
        "greeting": greeting(now, tz),
        "date": short_date(wd),
        "time": local_hhmm(now, tz),
        "recent": recent,
        "version": settings.railway_git_commit_sha,
    }
