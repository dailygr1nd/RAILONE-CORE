"""Signed sender and receiver execution-authority issuance."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping

from railone_crypto.canonical_json import canonical_json_bytes
from railone_crypto.signature_service import (
    ArtifactType,
    SignatureEnvelope,
    SignatureService,
)

from .models import ReceiverParticipationMode


def _require_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _artifact_id(prefix: str, payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest().upper()
    return f"{prefix}-{digest[:32]}"


class ExecutionAuthorityService:
    MAX_AUTHORITY_SECONDS = 15 * 60

    def __init__(self, signatures: SignatureService) -> None:
        self._signatures = signatures

    def issue_sender_authority(
        self,
        *,
        utt_id: str,
        quote_id: str,
        sender_actor_type: str,
        sender_reference: str,
        amount_minor: int,
        currency: str,
        origin_context: Mapping[str, Any],
        authorization_method: str,
        authorization_reference: str,
        signing_key_id: str,
        authorized_at: datetime,
        expires_at: datetime,
    ) -> SignatureEnvelope:
        issued = authorized_at.astimezone(timezone.utc)
        expiry = expires_at.astimezone(timezone.utc)
        self._validate_window(issued, expiry)
        if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
            raise TypeError("amount_minor must be an integer")
        if amount_minor <= 0:
            raise ValueError("amount_minor must be positive")

        core = {
            "utt_id": _require_text("utt_id", utt_id),
            "quote_id": _require_text("quote_id", quote_id),
            "sender_actor_type": _require_text(
                "sender_actor_type", sender_actor_type
            ),
            "sender_reference": _require_text(
                "sender_reference", sender_reference
            ),
            "amount_minor": amount_minor,
            "currency": _require_text("currency", currency).upper(),
            "origin_context": dict(origin_context),
            "authorization_method": _require_text(
                "authorization_method", authorization_method
            ),
            "authorization_reference": _require_text(
                "authorization_reference", authorization_reference
            ),
            "authorized_at": int(issued.timestamp()),
            "expires_at": int(expiry.timestamp()),
            "authority_scope": "EXECUTE_UTT",
            "custody_model": "NON_CUSTODIAL",
            "status": "ACTIVE",
        }
        payload = {"etk_s_id": _artifact_id("ETKS", core), **core}
        return self._signatures.sign_artifact(
            artifact_type=ArtifactType.ETK_S,
            payload=payload,
            key_id=signing_key_id,
            issued_at=issued,
        )

    def issue_receiver_participation(
        self,
        *,
        sender_authority: SignatureEnvelope,
        receiver_actor_type: str,
        receiver_reference: str,
        participation_mode: ReceiverParticipationMode,
        evidence_reference: str,
        signing_key_id: str,
        attested_at: datetime,
        expires_at: datetime,
    ) -> SignatureEnvelope:
        sender_result = self._signatures.verify_artifact(
            sender_authority,
            expected_artifact_type=ArtifactType.ETK_S,
        )
        if not sender_result.valid:
            raise PermissionError(
                f"sender authority rejected: {sender_result.reason}"
            )

        sender = sender_authority.payload
        issued = attested_at.astimezone(timezone.utc)
        expiry = expires_at.astimezone(timezone.utc)
        self._validate_window(issued, expiry)
        if int(expiry.timestamp()) > sender["expires_at"]:
            raise ValueError("ETK-R cannot outlive ETK-S")

        core = {
            "utt_id": sender["utt_id"],
            "etk_s_id": sender["etk_s_id"],
            "receiver_actor_type": _require_text(
                "receiver_actor_type", receiver_actor_type
            ),
            "receiver_reference": _require_text(
                "receiver_reference", receiver_reference
            ),
            "participation_mode": participation_mode.value,
            "receiver_confirmed": participation_mode.receiver_confirmed,
            "evidence_reference": _require_text(
                "evidence_reference", evidence_reference
            ),
            "amount_minor": sender["amount_minor"],
            "currency": sender["currency"],
            "attested_at": int(issued.timestamp()),
            "expires_at": int(expiry.timestamp()),
            "custody_model": "NON_CUSTODIAL",
            "status": "ACTIVE",
        }
        payload = {"etk_r_id": _artifact_id("ETKR", core), **core}
        return self._signatures.sign_artifact(
            artifact_type=ArtifactType.ETK_R,
            payload=payload,
            key_id=signing_key_id,
            issued_at=issued,
        )

    @classmethod
    def _validate_window(cls, issued: datetime, expiry: datetime) -> None:
        if issued.tzinfo is None or expiry.tzinfo is None:
            raise ValueError("authority timestamps must be timezone-aware")
        seconds = (expiry - issued).total_seconds()
        if seconds <= 0:
            raise ValueError("authority expiry must be after issuance")
        if seconds > cls.MAX_AUTHORITY_SECONDS:
            raise ValueError("authority window exceeds maximum TTL")
