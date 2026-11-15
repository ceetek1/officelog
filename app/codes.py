"""Rotating clock-in codes (spec §5, decision D2). Pure: no database, no clock, no framework.

This module is the single definition of the code algorithm. ``frontend/src/codes.ts`` is a line-by-
line copy for browsers; ``tests/fixtures/code_vectors.json`` keeps the two identical. Today only the
server makes codes (the TV fetches them from ``GET /api/kiosk/code``). A future offline mode can let
the TV keep its own secret and run ``codes.ts`` itself, without changing the QR format or the scan
API: only the ``SecretSource`` on the server changes.

Algorithm
---------
- ``day_secret = HMAC-SHA256(master, "kiosk:" + work_date)``         (work_date as YYYY-MM-DD)
- ``key(purpose) = HMAC-SHA256(day_secret, "purpose:" + purpose)``    (purpose = "qr" or "typed";
  separate keys so a typed code can never be replayed as a QR code or the other way round)
- ``code(key, window)`` = 6 digits by RFC 4226 dynamic truncation of
  ``HMAC-SHA256(key, window as 8-byte big-endian)``
- **QR:** ``window = floor(unix_seconds / 5)``; content ``ATT1.<window>.<code>``. Accepted for the
  current window and the one before (so at most 10 s old).
- **Typed:** ``window = floor(unix_seconds / 30)``; the 6 digits under the QR. Accepted for the
  current window, and for the previous one during the first ``TYPED_SLACK`` seconds of the new
  window, because typing 6 digits takes a few seconds.
- The work_date used for a window is the company-local date at the start of that window.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import struct
from collections.abc import Callable, Iterable
from datetime import date
from typing import Protocol

QR_STEP = 5
TYPED_STEP = 30
TYPED_SLACK = 5
QR_PREFIX = "ATT1"
_QR_RE = re.compile(r"^ATT1\.(\d{1,12})\.(\d{6})$")
_TYPED_RE = re.compile(r"^\d{6}$")


def day_secret(master: bytes, work_date: date) -> bytes:
    return hmac.new(master, b"kiosk:" + work_date.isoformat().encode(), hashlib.sha256).digest()


def purpose_key(secret: bytes, purpose: str) -> bytes:
    if purpose not in ("qr", "typed"):
        raise ValueError("purpose must be 'qr' or 'typed'")
    return hmac.new(secret, b"purpose:" + purpose.encode(), hashlib.sha256).digest()


def code6(key: bytes, window: int) -> str:
    """RFC 4226 dynamic truncation, with HMAC-SHA256, to 6 digits."""
    mac = hmac.new(key, struct.pack(">Q", window), hashlib.sha256).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def qr_window(unix_seconds: float) -> int:
    return int(unix_seconds // QR_STEP)


def typed_window(unix_seconds: float) -> int:
    return int(unix_seconds // TYPED_STEP)


def qr_content(secret: bytes, window: int) -> str:
    return f"{QR_PREFIX}.{window}.{code6(purpose_key(secret, 'qr'), window)}"


def typed_code(secret: bytes, window: int) -> str:
    return code6(purpose_key(secret, "typed"), window)


class SecretSource(Protocol):
    """Where day secrets come from. Returns every secret that may have made a code on this date.

    Now: one secret per day derived from ``MASTER_SECRET`` (``MasterSecretSource``).
    Later (offline mode): one per active kiosk, each kiosk holding its own secret.
    """

    def secrets_for(self, work_date: date) -> Iterable[bytes]: ...


class MasterSecretSource:
    def __init__(self, master: bytes):
        self._master = master

    def secrets_for(self, work_date: date) -> Iterable[bytes]:
        return (day_secret(self._master, work_date),)


DateOf = Callable[[float], date]  # unix seconds -> company-local date


def _matches(expected: Iterable[str], got: str) -> bool:
    ok = False
    for e in expected:
        ok |= hmac.compare_digest(e, got)
    return ok


def check_qr(content: str, now: float, source: SecretSource, date_of: DateOf) -> int | None:
    """Return the QR's window if it is valid now, else ``None``."""
    m = _QR_RE.match(content.strip())
    if not m:
        return None
    window, code = int(m.group(1)), m.group(2)
    current = qr_window(now)
    if window not in (current, current - 1):
        return None
    secrets = source.secrets_for(date_of(window * QR_STEP))
    if _matches((code6(purpose_key(s, "qr"), window) for s in secrets), code):
        return window
    return None


def check_typed(code: str, now: float, source: SecretSource, date_of: DateOf) -> int | None:
    """Return the typed code's window if it is valid now, else ``None``."""
    code = code.strip()
    if not _TYPED_RE.match(code):
        return None
    current = typed_window(now)
    windows = [current]
    if now - current * TYPED_STEP < TYPED_SLACK:
        windows.append(current - 1)
    for w in windows:
        secrets = source.secrets_for(date_of(w * TYPED_STEP))
        if _matches((code6(purpose_key(s, "typed"), w) for s in secrets), code):
            return w
    return None


def is_qr_shaped(text: str) -> bool:
    return bool(_QR_RE.match(text.strip()))
