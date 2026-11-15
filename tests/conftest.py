"""Test setup: a fresh Postgres database, migrated, with the app connecting as its restricted role.

Set TEST_DATABASE_ADMIN_URL to a Postgres server where you may create databases
(default: postgresql://postgres@localhost:5432/postgres).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ADMIN_URL = os.environ.get("TEST_DATABASE_ADMIN_URL", "postgresql://postgres@localhost:5432/postgres")
TEST_DB = "officelog_test"

_admin = make_url(ADMIN_URL)
OWNER_URL = _admin.set(database=TEST_DB).render_as_string(hide_password=False)

os.environ.update({
    "DATABASE_URL": OWNER_URL,
    "APP_DB_ROLE": "attendance_app_test",
    "APP_DB_PASSWORD": "test-app-password-123",
    "COOKIE_SECURE": "false",
    "FRONTEND_DIST": "",
    "BASE_URL": "https://attendance.test",
    "SCHEDULE_JSON": "",
    "HOLIDAYS": "2026-12-25",
    "MASTER_SECRET": "test-master-secret-0123456789abcdef",
})


def _plain(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture(scope="session", autouse=True)
def database():
    with psycopg.connect(_plain(ADMIN_URL), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{TEST_DB}" ENCODING \'UTF8\' TEMPLATE template0')
    from app.admin import migrate

    migrate()
    yield


OWNER_ENGINE_URL = "postgresql+psycopg://" + OWNER_URL.split("://", 1)[1]


@pytest.fixture
def owner():
    """An engine connected as the database owner (bypasses the app role's limits)."""
    eng = create_engine(OWNER_ENGINE_URL)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def clean(database, owner):
    from app.dbrole import TABLE_PRIVILEGES

    with owner.begin() as conn:
        conn.execute(text("SET LOCAL session_replication_role = replica"))  # lets us clear activity_log
        conn.execute(text("TRUNCATE " + ", ".join(TABLE_PRIVILEGES) + " RESTART IDENTITY CASCADE"))
    yield


# A Monday in the company timezone (Africa/Lagos is UTC+1).
MONDAY_0900_LAGOS = datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock():
    from app.clock import FixedClock

    return FixedClock(MONDAY_0900_LAGOS)


@pytest.fixture
def app(clock):
    from app.auth import get_clock
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_clock] = lambda: clock
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def make_user(owner):
    """Insert a user directly. Returns its id."""
    from app.security import hash_password

    def _make(name: str, role: str, email: str | None = None, password: str | None = None,
              active: bool = True) -> int:
        with owner.begin() as conn:
            return conn.execute(
                text("INSERT INTO users (name, role, email, password_hash, active) "
                     "VALUES (:n, :r, :e, :p, :a) RETURNING id"),
                {"n": name, "r": role, "e": email,
                 "p": hash_password(password) if password else None, "a": active},
            ).scalar_one()

    return _make


MD_EMAIL = "folake@company.test"
MD_PASSWORD = "correct horse battery"


@pytest.fixture
def md(make_user):
    return make_user("Folake Adeyemi", "md", MD_EMAIL, MD_PASSWORD)


@pytest.fixture
def session_for(owner, clock):
    """Sign a user in directly (phone sign-in arrives in Step 2). Returns (cookie, csrf)."""
    from app.security import new_token, token_hash

    def _sign_in(user_id: int) -> tuple[str, str]:
        token, csrf = new_token(), new_token()
        with owner.begin() as conn:
            conn.execute(
                text("INSERT INTO sessions (user_id, token_hash, csrf_token, created_at, expires_at) "
                     "VALUES (:u, :h, :c, :now, :exp)"),
                {"u": user_id, "h": token_hash(token), "c": csrf, "now": clock.now(),
                 "exp": clock.now() + timedelta(days=30)},
            )
        return token, csrf

    return _sign_in


def login_md(client, email: str = MD_EMAIL, password: str = MD_PASSWORD):
    return client.post("/api/auth/password-login", json={"email": email, "password": password})


@pytest.fixture
def invite_for(owner, clock):
    """Create an invite for a user directly. Returns the raw token."""
    from app.security import new_token, token_hash

    def _invite(user_id: int, hours: int = 48) -> str:
        token = new_token()
        with owner.begin() as conn:
            conn.execute(text("INSERT INTO invites (user_id, token_hash, created_at, expires_at) "
                              "VALUES (:u, :h, :now, :exp)"),
                         {"u": user_id, "h": token_hash(token), "now": clock.now(),
                          "exp": clock.now() + timedelta(hours=hours)})
        return token

    return _invite


def register_phone(client, token: str, phone=None, **kw):
    """Walk an invite through Face ID setup. Returns (response, phone)."""
    from tests.softauthn import Phone

    phone = phone or Phone()
    opts = client.post(f"/api/invites/{token}/options").json()
    cred = phone.create(opts["options"], **kw)
    r = client.post(f"/api/invites/{token}/register",
                    json={"challenge_id": opts["challenge_id"], "credential": cred, "privacy_ack": True})
    return r, phone


@pytest.fixture
def registered(client, make_user, invite_for):
    """A worker with a registered phone, signed in on ``client``. Returns (user_id, phone, csrf)."""
    def _reg(name: str = "Adaeze Obi", role: str = "worker"):
        uid = make_user(name, role)
        r, phone = register_phone(client, invite_for(uid))
        assert r.status_code == 200, r.text
        return uid, phone, r.json()["csrf_token"]

    return _reg
