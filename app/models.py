"""Database tables.

Times are stored as ``timestamptz`` (UTC). ``work_date`` is the calendar date in the company
timezone. The day view (late, absent, hours …) is never stored: ``app/rules`` calculates it.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROLES = ("worker", "manager", "md")
SCAN_KINDS = ("in", "out")
SCAN_SOURCES = ("qr", "typed", "paper")
PAPER_REASONS = ("tv_not_working", "no_smartphone", "phone_dead_or_forgotten")
REASON_TYPES = ("late", "absent", "missed_clock_out", "left_early")
DECISIONS = ("approved", "rejected")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[int]:
    return mapped_column(BigInteger, primary_key=True, autoincrement=True)


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = _pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))  # MD only
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)  # MD only; phones use passkeys
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        CheckConstraint(_in("role", ROLES), name="role_valid"),
        CheckConstraint("(role = 'md') = (email IS NOT NULL)", name="email_only_for_md"),
        CheckConstraint("(role = 'md') = (password_hash IS NOT NULL)", name="password_only_for_md"),
        # Exactly one active MD and one active manager.
        Index("uq_users_one_active_md_or_manager", "role", unique=True,
              postgresql_where=text("active AND role IN ('md', 'manager')")),
        Index("uq_users_email", func.lower(text("email")), unique=True,
              postgresql_where=text("email IS NOT NULL")),
    )


class Device(Base):
    """A worker's registered phone: one WebAuthn passkey credential."""

    __tablename__ = "devices"
    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    credential_id: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    transports: Mapped[list[str] | None] = mapped_column(ARRAY(String(20)))
    registered_at: Mapped[datetime] = _now()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("uq_devices_one_active_per_user", "user_id", unique=True,
              postgresql_where=text("revoked_at IS NULL")),
    )


class Invite(Base):
    __tablename__ = "invites"
    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # NULL = admin CLI
    created_at: Mapped[datetime] = _now()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Kiosk(Base):
    """The entrance TV. It is paired once with a single-use setup link; after that it holds a
    long-lived kiosk token in an httpOnly cookie. It never signs in and holds no code secret."""

    __tablename__ = "kiosks"
    id: Mapped[int] = _pk()
    token_hash: Mapped[bytes | None] = mapped_column(LargeBinary, unique=True)  # set when paired
    setup_token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    setup_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # NULL = admin CLI
    created_at: Mapped[datetime] = _now()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebauthnChallenge(Base):
    """A one-time WebAuthn challenge. ``purpose`` is register, login or clock.
    For clock challenges, ``data`` holds what the scan checked (kind, server time, window …)."""

    __tablename__ = "webauthn_challenges"
    id: Mapped[int] = _pk()
    challenge: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    purpose: Mapped[str] = mapped_column(String(10), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    invite_id: Mapped[int | None] = mapped_column(ForeignKey("invites.id"))
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("purpose IN ('register', 'login', 'clock')", name="purpose_valid"),
        Index("ix_webauthn_challenges_expires_at", "expires_at"),
    )


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"))  # phone sessions
    created_at: Mapped[datetime] = _now()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Scan(Base):
    """A recorded clock-in or clock-out. Append-only: the app's role cannot UPDATE or DELETE."""

    __tablename__ = "scans"
    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(3), nullable=False)
    server_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(5), nullable=False)
    kiosk_id: Mapped[int | None] = mapped_column(ForeignKey("kiosks.id"))
    kiosk_window: Mapped[int | None] = mapped_column(BigInteger)
    ip: Mapped[str | None] = mapped_column(String(45))
    # Time added by the manager or the MD from the paper sheet.
    entered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    paper_reason: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        UniqueConstraint("user_id", "work_date", "kind", name="uq_scans_one_per_kind_per_day"),
        CheckConstraint(_in("kind", SCAN_KINDS), name="kind_valid"),
        CheckConstraint(_in("source", SCAN_SOURCES), name="source_valid"),
        CheckConstraint(
            "(source = 'paper') = (entered_by IS NOT NULL AND paper_reason IS NOT NULL)",
            name="paper_needs_who_and_why",
        ),
        CheckConstraint(f"paper_reason IS NULL OR {_in('paper_reason', PAPER_REASONS)}",
                        name="paper_reason_valid"),
        Index("ix_scans_work_date", "work_date"),
    )


class ScanAttempt(Base):
    """Every scan attempt, including failures."""

    __tablename__ = "scan_attempts"
    id: Mapped[int] = _pk()
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    result: Mapped[str] = mapped_column(String(40), nullable=False)  # 'ok' or an error code
    method: Mapped[str | None] = mapped_column(String(5))  # 'qr' or 'typed'
    client_ms_to_scan: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _now()

    __table_args__ = (Index("ix_scan_attempts_created_at", "created_at"),)


class Reason(Base):
    __tablename__ = "reasons"
    id: Mapped[int] = _pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    claimed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    text: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()

    __table_args__ = (
        UniqueConstraint("user_id", "work_date", "type", name="uq_reasons_one_per_type_per_day"),
        CheckConstraint(_in("type", REASON_TYPES), name="type_valid"),
        CheckConstraint("(type = 'missed_clock_out') = (claimed_time IS NOT NULL)",
                        name="claimed_time_only_for_missed_clock_out"),
    )


class Decision(Base):
    """Append-only. The newest row for a reason is the one that counts."""

    __tablename__ = "decisions"
    id: Mapped[int] = _pk()
    reason_id: Mapped[int] = mapped_column(ForeignKey("reasons.id"), nullable=False, index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    is_override: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = _now()

    __table_args__ = (CheckConstraint(_in("decision", DECISIONS), name="decision_valid"),)


class ActivityLog(Base):
    """Append-only for everyone (grants + a trigger)."""

    __tablename__ = "activity_log"
    id: Mapped[int] = _pk()
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    entity: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(100))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _now()

    __table_args__ = (Index("ix_activity_log_created_at", "created_at"),)


class LoginFailure(Base):
    """Failed logins, for the lockout. ``key`` is e.g. ``email:x@y`` or ``device:<id>``."""

    __tablename__ = "login_failures"
    id: Mapped[int] = _pk()
    key: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_login_failures_key_time", "key", "created_at"),)
