"""Sign in and out. The MD uses email + password (spec §2). Phone sign-in (passkeys, decision D1)
arrives in Step 2."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app import activity, lockout
from app.auth import CurrentUser, current_user, end_session, get_clock, optional_user, start_session
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import User
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
