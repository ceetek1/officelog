"""Sessions, CSRF and role checks (spec §2, §8).

- The session cookie is httpOnly, SameSite=Lax and Secure (in production). It holds a random
  token; the database keeps only its SHA-256 hash.
- Every request that changes something must send the session's CSRF token in ``X-CSRF-Token``.
- Every endpoint declares which roles may call it with ``require_roles``. The backend checks
  this on every request; the UI hiding a button is never the check.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.clock import Clock, SystemClock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Session, User
from app.security import new_token, same, token_hash

COOKIE_NAME = "att_session"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

_system_clock = SystemClock()


def get_clock() -> Clock:
    """Overridden in tests to simulate any time."""
    return _system_clock


@dataclass
class CurrentUser:
    user: User
    session: Session

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def role(self) -> str:
        return self.user.role


def start_session(
    db: DbSession, response: Response, user: User, now: datetime, settings: Settings,
    device_id: int | None = None,
) -> Session:
    token = new_token()
    sess = Session(
        user_id=user.id,
        token_hash=token_hash(token),
        csrf_token=secrets.token_urlsafe(32),
        device_id=device_id,
        created_at=now,
        expires_at=now + timedelta(days=settings.session_days),
    )
    db.add(sess)
    db.flush()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return sess


def end_session(db: DbSession, response: Response, sess: Session | None, now: datetime) -> None:
    if sess is not None and sess.revoked_at is None:
        sess.revoked_at = now
    response.delete_cookie(COOKIE_NAME, path="/")


def _load_session(request: Request, db: DbSession, now: datetime) -> CurrentUser | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    row = db.execute(
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(Session.token_hash == token_hash(token))
    ).first()
    if row is None:
        return None
    sess, user = row
    if sess.revoked_at is not None or sess.expires_at <= now or not user.active:
        return None
    return CurrentUser(user=user, session=sess)


def optional_user(
    request: Request, db: DbSession = Depends(get_db), clock: Clock = Depends(get_clock)
) -> CurrentUser | None:
    return _load_session(request, db, clock.now())


NOT_LOGGED_IN = {"code": "not_logged_in", "message": "Please sign in."}


def authenticate(request: Request, db: DbSession, now: datetime) -> CurrentUser:
    """The signed-in user, with the CSRF check for requests that change something."""
    cu = _load_session(request, db, now)
    if cu is None:
        raise HTTPException(status_code=401, detail=NOT_LOGGED_IN)
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not same(sent, cu.session.csrf_token):
            raise HTTPException(status_code=403, detail={"code": "csrf", "message": "Please reload the page and try again."})
    return cu


def forbidden() -> HTTPException:
    return HTTPException(status_code=403, detail={"code": "forbidden", "message": "You can't do that."})


def current_user(
    request: Request, db: DbSession = Depends(get_db), clock: Clock = Depends(get_clock)
) -> CurrentUser:
    return authenticate(request, db, clock.now())


def require_roles(*roles: str) -> Callable[..., CurrentUser]:
    """Dependency: the caller must be signed in with one of ``roles``; otherwise 401 or 403."""

    def dep(cu: CurrentUser = Depends(current_user)) -> CurrentUser:
        if cu.role not in roles:
            raise forbidden()
        return cu

    dep.allowed_roles = frozenset(roles)  # type: ignore[attr-defined]  # read by the permissions test
    return dep


__all__ = [
    "COOKIE_NAME", "CSRF_HEADER", "CurrentUser", "current_user", "end_session", "get_clock",
    "get_settings", "optional_user", "require_roles", "start_session",
]
