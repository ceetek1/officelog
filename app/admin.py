"""Admin command line (spec §8).

    python -m app.admin migrate
    python -m app.admin create-md --name "Folake Adeyemi" --email folake@example.com
    python -m app.admin reset-md-password --email folake@example.com
    python -m app.admin create-manager --name "Emeka Okonkwo"
    python -m app.admin create-worker --name "Adaeze Obi"
    python -m app.admin reset-phone --name "Emeka Okonkwo"
    python -m app.admin create-tv-link
    python -m app.admin usage --from 2026-11-02 --to 2026-11-13

Passwords are read with a hidden prompt, or from standard input with ``--password-stdin``.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import timedelta

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app import activity
from app.clock import SystemClock
from app.config import get_settings
from app.db import app_engine, owner_engine
from app.dbrole import ensure_app_role
from app.models import Invite, User
from app.security import hash_password, new_token, token_hash

INVITE_LIFETIME = timedelta(hours=48)
TV_LINK_LIFETIME = timedelta(hours=24)
MIN_PASSWORD = 10


def _fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def migrate() -> None:
    """Bring the schema up to date and (re)apply the app role's privileges. Runs as the owner."""
    settings = get_settings()
    cfg = Config("alembic.ini")
    cfg.attributes["url"] = settings.database_url
    command.upgrade(cfg, "head")
    with owner_engine().begin() as conn:
        ensure_app_role(conn, settings.app_db_role, settings.app_db_password)
    print("Database is up to date.")


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        pw = sys.stdin.readline().rstrip("\n")
    else:
        pw = getpass.getpass("New password: ")
        if getpass.getpass("Repeat it: ") != pw:
            _fail("the two passwords are different")
    if len(pw) < MIN_PASSWORD:
        _fail(f"the password must be at least {MIN_PASSWORD} characters")
    return pw


def create_invite(db: DbSession, user_id: int, created_by: int | None, now=None) -> str:
    """Make a single-use invite (48 h). Returns the link; only the token's hash is stored."""
    settings = get_settings()
    now = now or SystemClock().now()
    token = new_token()
    inv = Invite(user_id=user_id, token_hash=token_hash(token), created_by=created_by,
                 created_at=now, expires_at=now + INVITE_LIFETIME)
    db.add(inv)
    db.flush()
    activity.log(db, actor_id=created_by, action="invite_create", entity="invite", entity_id=inv.id,
                 after={"user_id": user_id, "expires_at": inv.expires_at.isoformat()})
    return f"{settings.base_url}/invite/{token}"


def create_md(name: str, email: str, password_stdin: bool) -> None:
    name, email = name.strip(), email.strip().lower()
    if not name or "@" not in email:
        _fail("give a name and a valid email")
    password = _read_password(password_stdin)
    with DbSession(app_engine()) as db:
        user = User(name=name, email=email, role="md", password_hash=hash_password(password))
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            _fail("there is already an active MD, or that email is taken")
        activity.log(db, actor_id=None, action="user_add", entity="user", entity_id=user.id,
                     after={"name": name, "role": "md", "email": email})
        db.commit()
    print(f"Created MD {name} <{email}>. They can sign in at {get_settings().base_url}/md/login")


def reset_md_password(email: str, password_stdin: bool) -> None:
    email = email.strip().lower()
    with DbSession(app_engine()) as db:
        user = db.scalars(select(User).where(func.lower(User.email) == email, User.role == "md")).first()
        if user is None:
            _fail("no MD with that email")
        password = _read_password(password_stdin)
        user.password_hash = hash_password(password)
        activity.log(db, actor_id=None, action="password_reset", entity="user", entity_id=user.id)
        db.commit()
    print(f"Password changed for {email}.")


def create_manager(name: str) -> None:
    name = name.strip()
    if not name:
        _fail("give a name")
    with DbSession(app_engine()) as db:
        user = User(name=name, role="manager")
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            _fail("there is already an active manager (the MVP allows exactly one)")
        activity.log(db, actor_id=None, action="user_add", entity="user", entity_id=user.id,
                     after={"name": name, "role": "manager"})
        link = create_invite(db, user.id, created_by=None)
        db.commit()
    print(f"Created manager {name}.")
    print("Open this link on the manager's own phone within 48 hours (it works once):")
    print(link)


def create_worker(name: str) -> None:
    """The manager normally adds workers on the People screen; this does the same from here."""
    from app import people

    try:
        with DbSession(app_engine()) as db:
            user, link = people.add_worker(db, name, None, SystemClock().now())
            shown = user.name
            db.commit()
    except people.PeopleError as err:
        _fail(err.message)
    print(f"Created worker {shown}.")
    print("Open this link on their own phone within 48 hours (it works once):")
    print(link)


def reset_phone(name: str) -> None:
    """For when the manager loses their own phone (the People screen can't reset yourself)."""
    from app import people

    name = name.strip()
    with DbSession(app_engine()) as db:
        found = db.scalars(select(User).where(func.lower(User.name) == name.lower(), User.active.is_(True),
                                              User.role.in_(("worker", "manager")))).all()
        if not found:
            _fail(f"no active worker or manager called {name!r}")
        if len(found) > 1:
            _fail(f"more than one person is called {name!r}; use the People screen")
        try:
            user, link = people.reset_phone(db, found[0].id, None, SystemClock().now())
        except people.PeopleError as err:
            _fail(err.message)
        shown = user.name
        db.commit()
    print(f"Reset {shown}'s phone. Their old phone is signed out and can't clock in.")
    print("Open this link on their new phone within 48 hours (it works once):")
    print(link)


def create_tv_link() -> None:
    """A single-use link that pairs the entrance TV (24 hours); the manager can also make one."""
    from app import people

    with DbSession(app_engine()) as db:
        _, code, link = people.create_tv_link(db, None, SystemClock().now())
        db.commit()
    print("Open this link once in the TV's web browser within 24 hours:")
    print(link)
    print(f"Or open {get_settings().base_url}/tv on the TV and type the code {code}")


def _p(v) -> str:
    return "--" if v is None else f"{v}%"


def _s(ms) -> str:
    return "--" if ms is None else f"{ms / 1000:.1f} s"


def usage(start: str | None, end: str | None, now=None) -> None:
    """Spec §9: the same numbers as the MD's Usage page, per working day and in total."""
    from datetime import date

    from app.usage import RangeError, usage_report

    settings = get_settings()
    now = now or SystemClock().now()
    try:
        b = date.fromisoformat(end) if end else now.astimezone(settings.tz).date()
        a = date.fromisoformat(start) if start else b - timedelta(days=13)
    except ValueError:
        _fail("use dates like 2026-11-16")
    try:
        with DbSession(app_engine()) as db:
            r = usage_report(db, settings, a, b, now)
    except RangeError as err:
        _fail(str(err))
    t = r["totals"]
    print(f"Usage {r['from']} to {r['to']} ({r['working_days']} working days)")
    print()
    head = f"{'Day':<12}{'Active':>7}{'Both scans':>12}{'First try':>11}{'Tap to receipt':>16}" \
           f"{'Failed':>8}{'No clock-out':>14}{'Reasons':>9}{'Paper':>7}"
    print(head)
    print("-" * len(head))
    for d in r["days"]:
        print(f"{d['label']:<12}{d['active']:>7}{_p(d['both_pct']):>12}{_p(d['first_try_pct']):>11}"
              f"{_s(d['tap_to_receipt_ms']):>16}{d['failed']:>8}{d['missing_clock_out']:>14}{d['reasons']:>9}{d['paper']:>7}")
    print("-" * len(head))
    print(f"{'Total':<12}{t['active']:>7}{_p(t['both_pct']):>12}{_p(t['first_try_pct']):>11}"
          f"{_s(t['tap_to_receipt_ms']):>16}{t['failed']:>8}{t['missing_clock_out']:>14}{t['reasons']:>9}{t['paper']:>7}")
    print()
    print(f"Both scans: {t['both']} of {t['active']} person-days. First try: {t['first_try']} of {t['tries']}.")
    print(f"Reasons: {t['reasons']} sent, {t['reasons_approved']} approved, {t['reasons_rejected']} rejected, "
          f"{t['reasons_waiting']} waiting.")
    if r["failures"]:
        print("Failed scans by cause:")
        for f in r["failures"]:
            print(f"  {f['label']}: {f['count']}")
    else:
        print("No failed scans.")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m app.admin")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="update the database schema and the app role")
    c = sub.add_parser("create-md", help="create the MD (email + password)")
    c.add_argument("--name", required=True)
    c.add_argument("--email", required=True)
    c.add_argument("--password-stdin", action="store_true")
    r = sub.add_parser("reset-md-password", help="set a new password for the MD")
    r.add_argument("--email", required=True)
    r.add_argument("--password-stdin", action="store_true")
    m = sub.add_parser("create-manager", help="create the manager and print their invite link")
    m.add_argument("--name", required=True)
    w = sub.add_parser("create-worker", help="create a worker and print their invite link")
    w.add_argument("--name", required=True)
    rp = sub.add_parser("reset-phone", help="revoke a person's phone and print a new invite link")
    rp.add_argument("--name", required=True)
    sub.add_parser("create-tv-link", help="print a single-use link that pairs the entrance TV")
    u = sub.add_parser("usage", help="print the usage numbers (default: the last 14 days)")
    u.add_argument("--from", dest="start", help="first day, YYYY-MM-DD")
    u.add_argument("--to", dest="end", help="last day, YYYY-MM-DD (default today)")
    a = p.parse_args(argv)

    if a.cmd == "migrate":
        migrate()
    elif a.cmd == "create-md":
        create_md(a.name, a.email, a.password_stdin)
    elif a.cmd == "reset-md-password":
        reset_md_password(a.email, a.password_stdin)
    elif a.cmd == "create-manager":
        create_manager(a.name)
    elif a.cmd == "create-worker":
        create_worker(a.name)
    elif a.cmd == "reset-phone":
        reset_phone(a.name)
    elif a.cmd == "create-tv-link":
        create_tv_link()
    elif a.cmd == "usage":
        usage(a.start, a.end)


if __name__ == "__main__":
    main()
