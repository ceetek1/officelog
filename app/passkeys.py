"""Face ID / fingerprint sign-in with WebAuthn passkeys (decision D1).

Phones register a passkey on their built-in authenticator (``platform``), as a discoverable
credential, and every use requires user verification (Face ID, fingerprint or phone passcode).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, generate_challenge
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import Settings
from app.models import Device, User, WebauthnChallenge

LIFETIME = {"register": timedelta(minutes=5), "login": timedelta(minutes=2), "clock": timedelta(minutes=2)}
ALGS = [COSEAlgorithmIdentifier.ECDSA_SHA_256, COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256]

NOT_REGISTERED = "This phone isn't registered. Ask your manager to reset your phone."


class PasskeyError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def new_challenge(db: DbSession, purpose: str, now: datetime, **fields) -> WebauthnChallenge:
    ch = WebauthnChallenge(challenge=generate_challenge(), purpose=purpose, created_at=now,
                           expires_at=now + LIFETIME[purpose], **fields)
    db.add(ch)
    db.flush()
    return ch


def take_challenge(db: DbSession, challenge_id: int, purpose: str, now: datetime, **match) -> WebauthnChallenge:
    """Load an unused, unexpired challenge and mark it used (each challenge works once)."""
    q = select(WebauthnChallenge).where(
        WebauthnChallenge.id == challenge_id, WebauthnChallenge.purpose == purpose
    ).with_for_update()
    for col, val in match.items():
        q = q.where(getattr(WebauthnChallenge, col) == val)
    ch = db.scalars(q).first()
    if ch is None or ch.used_at is not None or ch.expires_at <= now:
        raise PasskeyError("challenge_expired", "That took too long. Please try again.")
    ch.used_at = now
    return ch


def _json(options) -> dict:
    return json.loads(options_to_json(options))


def registration_options(settings: Settings, user: User, ch: WebauthnChallenge) -> dict:
    return _json(generate_registration_options(
        rp_id=settings.rp_id,
        rp_name=settings.company_name or "Attendance",
        user_id=f"user-{user.id}".encode(),
        user_name=user.name,
        user_display_name=user.name,
        challenge=ch.challenge,
        timeout=120_000,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        supported_pub_key_algs=ALGS,
    ))


def verify_registration(settings: Settings, ch: WebauthnChallenge, credential: dict) -> Device:
    try:
        v = verify_registration_response(
            credential=credential,
            expected_challenge=ch.challenge,
            expected_rp_id=settings.rp_id,
            expected_origin=settings.origins,
            require_user_verification=True,
            supported_pub_key_algs=ALGS,
        )
    except (WebAuthnException, ValueError, KeyError, TypeError) as exc:
        raise PasskeyError("face_id_failed", "Face ID setup didn't work. Please try again.") from exc
    transports = (credential.get("response") or {}).get("transports") or []
    return Device(
        credential_id=v.credential_id,
        public_key=v.credential_public_key,
        sign_count=v.sign_count,
        transports=[str(t)[:20] for t in transports][:5] or None,
    )


def authentication_options(settings: Settings, ch: WebauthnChallenge, device: Device | None = None) -> dict:
    allow = None
    if device is not None:
        allow = [PublicKeyCredentialDescriptor(
            id=device.credential_id,
            transports=[AuthenticatorTransport(t) for t in (device.transports or [])
                        if t in AuthenticatorTransport._value2member_map_] or None,
        )]
    return _json(generate_authentication_options(
        rp_id=settings.rp_id,
        challenge=ch.challenge,
        timeout=60_000,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.REQUIRED,
    ))


def credential_id_of(credential: dict) -> bytes:
    try:
        return base64url_to_bytes(credential["rawId"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PasskeyError("bad_request", "Please try again.") from exc


def verify_assertion(settings: Settings, ch: WebauthnChallenge, device: Device, credential: dict) -> None:
    """Check the phone's signature; updates the device's sign count."""
    if credential_id_of(credential) != device.credential_id:
        raise PasskeyError("face_id_failed", "Face ID didn't match this phone. Please try again.")
    try:
        v = verify_authentication_response(
            credential=credential,
            expected_challenge=ch.challenge,
            expected_rp_id=settings.rp_id,
            expected_origin=settings.origins,
            credential_public_key=device.public_key,
            credential_current_sign_count=device.sign_count,
            require_user_verification=True,
        )
    except (WebAuthnException, ValueError, KeyError, TypeError) as exc:
        raise PasskeyError("face_id_failed", "Face ID didn't work. Please try again.") from exc
    device.sign_count = v.new_sign_count


def to_http(err: PasskeyError, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": err.code, "message": err.message})
