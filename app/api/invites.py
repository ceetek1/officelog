"""Invites: a worker opens the link on their own phone and sets up Face ID (spec §4.1, D1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from app import activity, passkeys
from app.auth import get_clock, start_session
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Device, Invite, User
from app.security import token_hash

router = APIRouter(prefix="/api/invites", tags=["invites"])

INVALID = {"code": "invite_invalid",
           "message": "This invite link has expired or was already used. Ask your manager for a new one."}


def _invite(db: DbSession, token: str, *, lock: bool = False) -> tuple[Invite, User] | None:
    q = select(Invite, User).join(User, User.id == Invite.user_id).where(Invite.token_hash == token_hash(token))
    if lock:
        q = q.with_for_update(of=Invite)
    return db.execute(q).first()


def _usable(db: DbSession, token: str, now, *, lock: bool = False) -> tuple[Invite, User]:
    row = _invite(db, token, lock=lock)
    if row is None:
        raise HTTPException(status_code=404, detail=INVALID)
    inv, user = row
    if inv.used_at is not None or inv.expires_at <= now or not user.active or user.role == "md":
        raise HTTPException(status_code=410, detail=INVALID)
    return inv, user


@router.get("/{token}")
def invite_info(
    token: str, db: DbSession = Depends(get_db), clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    inv, user = _usable(db, token, clock.now())
    by = db.get(User, inv.created_by) if inv.created_by else None
    return {"name": user.name, "invited_by": by.name if by else None, "company": settings.company_name}


@router.post("/{token}/options")
def register_options(
    token: str, db: DbSession = Depends(get_db), clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    inv, user = _usable(db, token, now)
    ch = passkeys.new_challenge(db, "register", now, user_id=user.id, invite_id=inv.id)
    options = passkeys.registration_options(settings, user, ch)
    db.commit()
    return {"challenge_id": ch.id, "options": options}


class Register(BaseModel):
    challenge_id: int
    credential: dict
    privacy_ack: bool


@router.post("/{token}/register")
def register(
    token: str, body: Register, response: Response,
    db: DbSession = Depends(get_db), clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    if not body.privacy_ack:
        raise HTTPException(status_code=400, detail={"code": "privacy_ack", "message": "Please read the privacy notice first."})
    inv, user = _usable(db, token, now, lock=True)
    try:
        ch = passkeys.take_challenge(db, body.challenge_id, "register", now, invite_id=inv.id)
        device = passkeys.verify_registration(settings, ch, body.credential)
    except passkeys.PasskeyError as err:
        db.commit()
        raise passkeys.to_http(err) from err

    if db.scalars(select(Device.id).where(Device.credential_id == device.credential_id)).first():
        raise HTTPException(status_code=409, detail={"code": "already_registered", "message": "This phone is already registered."})

    # One active device per person: a new registration replaces any old one.
    db.execute(update(Device).where(Device.user_id == user.id, Device.revoked_at.is_(None)).values(revoked_at=now))
    device.user_id = user.id
    device.registered_at = now
    db.add(device)
    inv.used_at = now
    db.flush()
    activity.log(db, actor_id=user.id, action="device_register", entity="device", entity_id=device.id,
                 after={"user_id": user.id, "invite_id": inv.id, "privacy_ack": True})
    sess = start_session(db, response, user, now, settings, device_id=device.id)
    db.commit()
    return {"user": {"id": user.id, "name": user.name, "role": user.role}, "csrf_token": sess.csrf_token,
            "company": settings.company_name}
