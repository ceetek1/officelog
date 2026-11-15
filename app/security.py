"""Hashing and random tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2id with the library's recommended (RFC 9106 low-memory) parameters.
_hasher = PasswordHasher()
# Used so a login for an unknown email takes as long as one for a known email.
_DUMMY_HASH = _hasher.hash("not-a-real-password-0")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    """32 random bytes, URL-safe."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    """Only this SHA-256 hash of a token is stored."""
    return hashlib.sha256(token.encode()).digest()


def same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
