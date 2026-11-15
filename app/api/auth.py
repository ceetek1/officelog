"""Sign in and out. The MD uses email + password (spec §2); phones use Face ID passkeys (D1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app import activity, lockout, passkeys
from app.auth import CurrentUser, current_user, end_session, get_clock, optional_user, start_session
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Device, User
from app.security import verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class PasswordLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


def _me(user: User | None, csrf: str | None) -> dict:
    return {
        "user": None if user is None else {"id": user.id, "name": user.name, "role": user.role},
        "csrf_token": csrf,
        "company": get_settings().company_name,
    }


@router.post("/password-login")
def password_login(
    body: PasswordLogin,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    email = body.email.strip().lower()
    key = f"email:{email}"

    until = lockout.check(db, key, now)
    if until is not None:
        activity.log(db, actor_id=None, action="login_locked", entity="login", entity_id=email)
        db.commit()
        minutes = max(1, int((until - now).total_seconds() // 60) + 1)
        raise HTTPException(
            status_code=429,
            detail={"code": "locked", "message": f"Too many tries. Try again in {minutes} min."},
        )

    user = db.scalars(
        select(User).where(func.lower(User.email) == email, User.role == "md")
    ).first()
    ok = verify_password(user.password_hash if user else None, body.password)
    if not ok or user is None or not user.active:
        lockout.record_failure(db, key, now)
        activity.log(db, actor_id=None, action="login_failed", entity="login", entity_id=email,
                     after={"ip": request.client.host if request.client else None})
        db.commit()
        raise HTTPException(status_code=401, detail={"code": "bad_login", "message": "Wrong email or password."})

    sess = start_session(db, response, user, now, settings)
    db.commit()
    return _me(user, sess.csrf_token)


@router.post("/logout")
def logout(
    response: Response,
    cu: CurrentUser = Depends(current_user),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> dict:
    end_session(db, response, cu.session, clock.now())
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(cu: CurrentUser | None = Depends(optional_user)) -> dict:
    """Who is signed in. Returns ``{"user": null}`` when nobody is (not an error)."""
    if cu is None:
        return _me(None, None)
    return _me(cu.user, cu.session.csrf_token)


class PasskeyLogin(BaseModel):
    challenge_id: int
    credential: dict


@router.post("/passkey/options")
def passkey_options(
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Start a Face ID sign-in. Any passkey for this site may answer (it says who it is)."""
    ch = passkeys.new_challenge(db, "login", clock.now())
    options = passkeys.authentication_options(settings, ch)
    db.commit()
    return {"challenge_id": ch.id, "options": options}


@router.post("/passkey/login")
def passkey_login(
    body: PasskeyLogin,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    try:
        cred_id = passkeys.credential_id_of(body.credential)
    except passkeys.PasskeyError as err:
        raise passkeys.to_http(err) from err
    key = "credential:" + cred_id.hex()[:200]
    if lockout.check(db, key, now) is not None:
        activity.log(db, actor_id=None, action="login_locked", entity="device", entity_id=cred_id.hex()[:100])
        db.commit()
        raise HTTPException(status_code=429, detail={"code": "locked", "message": "Too many tries. Try again in 15 min."})

    def failed(code: str, message: str, user_id: int | None = None) -> HTTPException:
        lockout.record_failure(db, key, now)
        activity.log(db, actor_id=None, action="login_failed", entity="device", entity_id=cred_id.hex()[:100],
                     after={"reason": code, "user_id": user_id,
                            "ip": request.client.host if request.client else None})
        db.commit()
        return HTTPException(status_code=401, detail={"code": code, "message": message})

    try:
        ch = passkeys.take_challenge(db, body.challenge_id, "login", now)
    except passkeys.PasskeyError as err:
        db.commit()
        raise passkeys.to_http(err) from err

    row = db.execute(
        select(Device, User).join(User, User.id == Device.user_id)
        .where(Device.credential_id == cred_id, Device.revoked_at.is_(None), User.active.is_(True))
    ).first()
    if row is None:
        raise failed("phone_not_registered", passkeys.NOT_REGISTERED)
    device, user = row
    try:
        passkeys.verify_assertion(settings, ch, device, body.credential)
    except passkeys.PasskeyError as err:
        raise failed(err.code, err.message, user.id) from err
    sess = start_session(db, response, user, now, settings, device_id=device.id)
    db.commit()
    return _me(user, sess.csrf_token)
