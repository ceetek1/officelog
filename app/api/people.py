"""People (spec §2 "Adds, deactivates workers; resets a lost phone", §4.4): the manager only.

The logic lives in ``app/people.py`` (shared with the admin command line).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import people
from app.auth import CurrentUser, get_clock, require_roles
from app.clock import Clock
from app.config import Settings, get_settings
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/people", tags=["people"])

MANAGER = require_roles("manager")


def _http(err: people.PeopleError) -> HTTPException:
    return HTTPException(status_code=err.status, detail={"code": err.code, "message": err.message})


def _expires(inv_expires, tz) -> str:
    local = inv_expires.astimezone(tz)
    return f"{local:%a} {local.day} {local:%b}, {local:%H:%M}"


@router.get("")
def list_people(
    cu: CurrentUser = Depends(MANAGER),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Everyone who clocks in, with where their phone stands: Active, Invited, Expired or Off."""
    now = clock.now()
    users = db.scalars(select(User).where(User.role.in_(("worker", "manager")))).all()
    phones = people.phone_status(db, list(users), now)
    out = []
    for u in users:
        ph = phones[u.id]
        out.append({"id": u.id, "name": u.name, "role": u.role, "status": ph["status"], "label": ph["label"],
                    "is_me": u.id == cu.id,
                    "invite_expires": _expires(ph["invite_expires_at"], settings.tz)
                    if ph["invite_expires_at"] else None})
    out.sort(key=lambda p: (p["status"] == "off", p["name"].lower()))
    return {"people": out, "active_count": sum(1 for p in out if p["status"] != "off")}


class NewPerson(BaseModel):
    name: str = Field(min_length=1, max_length=200)


def _invite_reply(user: User, link: str, now, settings: Settings) -> dict:
    return {"id": user.id, "name": user.name, "link": link,
            "expires": _expires(people.invite_expiry(now), settings.tz)}


@router.post("")
def add_person(
    body: NewPerson,
    cu: CurrentUser = Depends(MANAGER),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    now = clock.now()
    try:
        user, link = people.add_worker(db, body.name, cu.id, now)
    except people.PeopleError as err:
        raise _http(err) from None
    db.commit()
    return _invite_reply(user, link, now, settings)


@router.post("/{user_id}/reset-phone")
def reset_phone(
    user_id: int,
    cu: CurrentUser = Depends(MANAGER),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Also used for "New Invite Link" when an invite expired before it was used."""
    now = clock.now()
    try:
        user, link = people.reset_phone(db, user_id, cu.id, now)
    except people.PeopleError as err:
        raise _http(err) from None
    db.commit()
    return _invite_reply(user, link, now, settings)


@router.post("/{user_id}/deactivate")
def deactivate(
    user_id: int,
    cu: CurrentUser = Depends(MANAGER),
    db: DbSession = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> dict:
    try:
        user = people.deactivate(db, user_id, cu.id, clock.now())
    except people.PeopleError as err:
        raise _http(err) from None
    db.commit()
    return {"id": user.id, "name": user.name, "active": False}
