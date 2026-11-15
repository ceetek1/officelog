"""The app's own database role and what it may do (builder's choice B1).

Migrations run as the database owner. The web app connects as ``APP_DB_ROLE``, which gets only
the privileges listed here. Append-only tables get SELECT and INSERT, never UPDATE or DELETE, so
"nobody edits a recorded time" and the append-only activity log are enforced by the database.

``ensure_app_role`` is idempotent; the container runs it on every start, after migrations.
"""

from __future__ import annotations

from sqlalchemy import Connection, text

READ_INSERT = ("SELECT", "INSERT")
READ_WRITE = ("SELECT", "INSERT", "UPDATE")
READ_WRITE_DELETE = ("SELECT", "INSERT", "UPDATE", "DELETE")

# Every table must be listed. A test checks this against the models.
TABLE_PRIVILEGES: dict[str, tuple[str, ...]] = {
    "users": READ_WRITE,
    "devices": READ_WRITE,
    "invites": READ_WRITE,
    "kiosks": READ_WRITE,
    "sessions": READ_WRITE,
    "scans": READ_INSERT,  # recorded times are never edited (paper times are new rows, D3)
    "scan_attempts": READ_INSERT,
    "reasons": READ_WRITE,  # editable while pending
    "decisions": READ_INSERT,  # append-only; newest wins
    "activity_log": READ_INSERT,  # append-only
    "login_failures": READ_WRITE_DELETE,
    "webauthn_challenges": READ_WRITE_DELETE,
}


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def ensure_app_role(conn: Connection, role: str, password: str) -> None:
    """Create or update the app role and (re)apply its privileges. Run as the database owner."""
    q = _quote_ident(role)
    exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).first()
    # Passwords can't be bound parameters in CREATE/ALTER ROLE; quote as a literal.
    literal = "'" + password.replace("'", "''") + "'"
    if exists:
        conn.execute(text(f"ALTER ROLE {q} WITH LOGIN PASSWORD {literal}"))
    else:
        conn.execute(text(f"CREATE ROLE {q} WITH LOGIN PASSWORD {literal}"))
    db = conn.execute(text("SELECT current_database()")).scalar_one()
    conn.execute(text(f"GRANT CONNECT ON DATABASE {_quote_ident(db)} TO {q}"))
    conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {q}"))
    for table, privs in TABLE_PRIVILEGES.items():
        t = _quote_ident(table)
        conn.execute(text(f"REVOKE ALL ON {t} FROM {q}"))
        conn.execute(text(f"GRANT {', '.join(privs)} ON {t} TO {q}"))
    conn.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {q}"))
    # Never let the app touch the migration bookkeeping.
    conn.execute(text(f"REVOKE ALL ON alembic_version FROM {q}"))
