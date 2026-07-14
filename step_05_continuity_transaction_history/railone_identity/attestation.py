"""Institutional Ed25519 attestation validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from railone_crypto.signature_service import (
    ArtifactType,
    SignatureEnvelope,
    SignatureService,
)

from .models import TrustTier


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class AttestationValidationResult:
    valid: bool
    reason: str
    claims: Mapping[str, Any] | None = None


class IdentityAttestationVerifier:
    def __init__(self, signatures: SignatureService) -> None:
        self._signatures = signatures

    def verify(
        self,
        envelope: SignatureEnvelope,
        *,
        expected_provider_id: str,
        at: datetime | None = None,
    ) -> AttestationValidationResult:
        signature_result = self._signatures.verify_artifact(
            envelope,
            expected_artifact_type=ArtifactType.IDENTITY_ATTESTATION,
        )
        if not signature_result.valid:
            return AttestationValidationResult(False, signature_result.reason)

        claims = envelope.payload
        required_strings = (
            "attestation_id",
            "provider_id",
            "provider_subject_reference",
            "verification_reference",
            "country_code",
            "verification_result",
            "trust_tier",
            "evidence_sha256",
        )
        for field in required_strings:
            if not isinstance(claims.get(field), str) or not claims[field].strip():
                return AttestationValidationResult(False, f"{field.upper()}_INVALID")

        if claims["provider_id"] != expected_provider_id:
            return AttestationValidationResult(False, "PROVIDER_MISMATCH")
        if claims["provider_id"] != envelope.protected.get("iss"):
            return AttestationValidationResult(False, "ATTESTATION_ISSUER_MISMATCH")
        if claims["verification_result"] != "VERIFIED":
            return AttestationValidationResult(False, "IDENTITY_NOT_VERIFIED")

        try:
            TrustTier(claims["trust_tier"])
        except ValueError:
            return AttestationValidationResult(False, "TRUST_TIER_INVALID")

        if not _SHA256_PATTERN.fullmatch(claims["evidence_sha256"]):
            return AttestationValidationResult(False, "EVIDENCE_HASH_INVALID")

        issued_at = claims.get("issued_at")
        expires_at = claims.get("expires_at")
        if not isinstance(issued_at, int) or not isinstance(expires_at, int):
            return AttestationValidationResult(False, "ATTESTATION_TIME_INVALID")
        if expires_at <= issued_at:
            return AttestationValidationResult(False, "ATTESTATION_WINDOW_INVALID")

        instant = int((at or datetime.now(timezone.utc)).timestamp())
        if instant < issued_at:
            return AttestationValidationResult(False, "ATTESTATION_NOT_YET_VALID")
        if instant >= expires_at:
            return AttestationValidationResult(False, "ATTESTATION_EXPIRED")

        return AttestationValidationResult(True, "VALID", claims=dict(claims))
