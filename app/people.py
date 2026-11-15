"""People and the entrance TV (spec §4.4, §11 step 5). Used by the manager's screens and the
admin command line, so both behave the same and both write to the activity log.

- **Add a worker:** a name, then a one-time invite link (48 h; only the token's hash is stored).
- **Deactivate:** the person can't sign in or scan; their sessions, phone and open invites stop
  working at once. Their history is kept.
- **Reset phone:** the phone's passkey and every session are revoked, open invites are cancelled,
  and a new invite is made. The MD sees it in the activity log (a reset could hand an account to
  someone else).
- **TV setup link:** single use, 24 hours. The code in it is short enough to type on a TV remote.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app import activity
from app.admin import INVITE_LIFETIME, TV_LINK_LIFETIME, create_invite
from app.config import get_settings
from app.models import Device, Invite, Kiosk, Session, User
from app.security import token_hash

# No 0/O, 1/I/L: easy to read off a phone and type with a TV remote.
TV_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
TV_CODE_LENGTH = 10  # about 50 bits; single use, 24 hours


class PeopleError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name or "").strip()
    if not name:
        raise PeopleError(400, "name_needed", "Type the person's name.")
    if len(name) > 100:
        raise PeopleError(400, "name_too_long", "That name is too long.")
    return name


def add_worker(db: DbSession, name: str, actor_id: int | None, now: datetime) -> tuple[User, str]:
    user = User(name=clean_name(name), role="worker", created_at=now)
    db.add(user)
    db.flush()
    activity.log(db, actor_id=actor_id, action="user_add", entity="user", entity_id=user.id,
                 after={"user_id": user.id, "name": user.name, "role": "worker"})
    return user, create_invite(db, user.id, created_by=actor_id, now=now)


def add_manager(db: DbSession, name: str, actor_id: int | None, now: datetime) -> tuple[User, str]:
    """The one manager (spec §2, decision D6). Refused while an active manager exists; the database's
    unique index enforces it too, so two clicks at once can't make two managers."""
    name = clean_name(name)
    existing = db.scalars(select(User).where(User.role == "manager", User.active.is_(True))).first()
    if existing is not None:
        raise PeopleError(409, "manager_exists", f"{existing.name} is already the manager. There can be only one.")
    user = User(name=name, role="manager", created_at=now)
    db.add(user)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise PeopleError(409, "manager_exists", "There is already a manager. There can be only one.") from None
    activity.log(db, actor_id=actor_id, action="user_add", entity="user", entity_id=user.id,
                 after={"user_id": user.id, "name": user.name, "role": "manager"})
    return user, create_invite(db, user.id, created_by=actor_id, now=now)


def phone_status(db: DbSession, users: list[User], now: datetime) -> dict[int, dict]:
    """Where each person's phone stands: active (Face ID set up), invited, expired / no phone, or off."""
    ids = [u.id for u in users]
    with_phone = set(db.scalars(select(Device.user_id).where(Device.revoked_at.is_(None), Device.user_id.in_(ids))))
    latest = dict(db.execute(
        select(Invite.user_id, func.max(Invite.expires_at))
        .where(Invite.used_at.is_(None), Invite.user_id.in_(ids)).group_by(Invite.user_id)).all())
    out = {}
    for u in users:
        if not u.active:
            status, label = "off", "Off"
        elif u.id in with_phone:
            status, label = "active", "Active"
        elif latest.get(u.id) and latest[u.id] > now:
            status, label = "invited", "Invited"
        else:
            status, label = "expired", "No phone" if u.id not in latest else "Expired"
        out[u.id] = {"status": status, "label": label,
                     "invite_expires_at": latest[u.id] if status == "invited" else None}
    return out


def _cancel_open_invites(db: DbSession, user_id: int, now: datetime) -> None:
    db.execute(update(Invite).where(Invite.user_id == user_id, Invite.used_at.is_(None),
                                    Invite.expires_at > now).values(expires_at=now))


def _revoke_sessions(db: DbSession, user_id: int, now: datetime) -> int:
    return db.execute(update(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
                      .values(revoked_at=now)).rowcount


def _revoke_device(db: DbSession, user_id: int, now: datetime) -> int | None:
    dev = db.scalars(select(Device).where(Device.user_id == user_id, Device.revoked_at.is_(None))).first()
    if dev is None:
        return None
    dev.revoked_at = now
    return dev.id


def person_for_change(db: DbSession, user_id: int, actor_id: int | None) -> User:
    """A worker or manager the actor may reset or deactivate (locked for the change)."""
    user = db.scalars(select(User).where(User.id == user_id).with_for_update()).first()
    if user is None or user.role == "md":
        raise PeopleError(404, "not_found", "That person isn't in the list.")
    if not user.active:
        raise PeopleError(409, "deactivated", f"{user.name} is deactivated.")
    if actor_id is not None and user.id == actor_id:
        raise PeopleError(409, "not_yourself", "You can't do this to yourself. Ask the developer.")
    return user


def deactivate(db: DbSession, user_id: int, actor_id: int | None, now: datetime) -> User:
    user = person_for_change(db, user_id, actor_id)
    if user.role == "manager":
        raise PeopleError(409, "manager", "The manager can only be changed by the developer.")
    user.active = False
    device_id = _revoke_device(db, user.id, now)
    sessions = _revoke_sessions(db, user.id, now)
    _cancel_open_invites(db, user.id, now)
    activity.log(db, actor_id=actor_id, action="user_deactivate", entity="user", entity_id=user.id,
                 before={"user_id": user.id, "active": True},
                 after={"user_id": user.id, "active": False, "device_id": device_id, "sessions_revoked": sessions})
    return user


def reset_phone(db: DbSession, user_id: int, actor_id: int | None, now: datetime) -> tuple[User, str]:
    """Revoke the phone and every session, cancel open invites, make a new invite."""
    user = person_for_change(db, user_id, actor_id)
    device_id = _revoke_device(db, user.id, now)
    sessions = _revoke_sessions(db, user.id, now)
    _cancel_open_invites(db, user.id, now)
    activity.log(db, actor_id=actor_id, action="device_reset", entity="user", entity_id=user.id,
                 before={"user_id": user.id, "device_id": device_id},
                 after={"user_id": user.id, "device_id": None, "sessions_revoked": sessions})
    return user, create_invite(db, user.id, created_by=actor_id, now=now)


def invite_expiry(now: datetime) -> datetime:
    return now + INVITE_LIFETIME


# ---- Entrance TV ----

def new_tv_code() -> str:
    return "".join(secrets.choice(TV_CODE_ALPHABET) for _ in range(TV_CODE_LENGTH))


def format_tv_code(code: str) -> str:
    return f"{code[:5]}-{code[5:]}"


def normalize_tv_code(typed: str) -> str:
    """'abcde-fghjk ' -> 'ABCDEFGHJK' (people type it on a TV remote)."""
    return re.sub(r"[^A-Za-z0-9]", "", typed or "").upper()


def create_tv_link(db: DbSession, actor_id: int | None, now: datetime) -> tuple[Kiosk, str, str]:
    """A single-use TV setup link. Returns (kiosk, code as shown, link). Only the code's hash is kept."""
    code = new_tv_code()
    kiosk = Kiosk(setup_token_hash=token_hash(code), setup_expires_at=now + TV_LINK_LIFETIME,
                  created_by=actor_id, created_at=now)
    db.add(kiosk)
    db.flush()
    activity.log(db, actor_id=actor_id, action="kiosk_create", entity="kiosk", entity_id=kiosk.id,
                 after={"kiosk_id": kiosk.id, "expires_at": kiosk.setup_expires_at.isoformat()})
    shown = format_tv_code(code)
    return kiosk, shown, f"{get_settings().base_url}/tv/pair/{shown}"


def revoke_tv(db: DbSession, kiosk_id: int, actor_id: int | None, now: datetime) -> Kiosk:
    kiosk = db.scalars(select(Kiosk).where(Kiosk.id == kiosk_id).with_for_update()).first()
    if kiosk is None or kiosk.revoked_at is not None:
        raise PeopleError(404, "not_found", "That TV was already removed.")
    kiosk.revoked_at = now
    activity.log(db, actor_id=actor_id, action="kiosk_revoke", entity="kiosk", entity_id=kiosk.id,
                 before={"kiosk_id": kiosk.id, "paired": kiosk.paired_at is not None},
                 after={"kiosk_id": kiosk.id, "revoked": True})
    return kiosk


ONLINE_WITHIN = timedelta(minutes=2)  # the TV polls every second; last_seen is written once a minute
