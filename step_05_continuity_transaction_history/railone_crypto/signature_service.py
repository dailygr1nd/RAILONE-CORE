"""Versioned, domain-separated Ed25519 signatures for RailOne artifacts."""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .canonical_json import canonical_json_bytes
from .key_provider import KeyPurpose, KeyStatus, SigningKeyProvider


class ArtifactType(StrEnum):
    QUOTE = "railone.quote"
    UTT = "railone.utt"
    RTT = "railone.rtt"
    ETK_S = "railone.etk_s"
    ETK_R = "railone.etk_r"
    EXECUTION_EVENT = "railone.execution_event"
    IDENTITY_ATTESTATION = "railone.identity_attestation"
    SETTLEMENT_EVIDENCE = "railone.settlement_evidence"
    REPLAY_CHECKPOINT = "railone.replay_checkpoint"


_PURPOSE_BY_ARTIFACT = {
    ArtifactType.QUOTE: KeyPurpose.QUOTE_SIGNING,
    ArtifactType.UTT: KeyPurpose.EXECUTION_SIGNING,
    ArtifactType.RTT: KeyPurpose.EXECUTION_SIGNING,
    ArtifactType.ETK_S: KeyPurpose.EXECUTION_SIGNING,
    ArtifactType.ETK_R: KeyPurpose.EXECUTION_SIGNING,
    ArtifactType.EXECUTION_EVENT: KeyPurpose.EXECUTION_SIGNING,
    ArtifactType.IDENTITY_ATTESTATION: KeyPurpose.IDENTITY_SIGNING,
    ArtifactType.SETTLEMENT_EVIDENCE: KeyPurpose.SETTLEMENT_SIGNING,
    ArtifactType.REPLAY_CHECKPOINT: KeyPurpose.REPLAY_SIGNING,
}

_DOMAIN_PREFIX = b"RAILONE-SIGNED-ARTIFACT-V1\x00"


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


@dataclass(frozen=True, slots=True)
class SignatureEnvelope:
    protected: Mapping[str, Any]
    payload: Mapping[str, Any]
    signature: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "protected", _freeze(self.protected))
        object.__setattr__(self, "payload", _freeze(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "protected": _thaw(self.protected),
            "payload": _thaw(self.payload),
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SignatureEnvelope":
        protected = value.get("protected")
        payload = value.get("payload")
        signature = value.get("signature")

        if not isinstance(protected, Mapping):
            raise ValueError("protected header must be an object")
        if not isinstance(payload, Mapping):
            raise ValueError("payload must be an object")
        if not isinstance(signature, str) or not signature:
            raise ValueError("signature must be a non-empty string")

        return cls(protected=protected, payload=payload, signature=signature)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    valid: bool
    reason: str
    key_id: str | None = None
    artifact_type: ArtifactType | None = None


class SignatureService:
    def __init__(self, key_provider: SigningKeyProvider) -> None:
        self._keys = key_provider

    def sign_artifact(
        self,
        *,
        artifact_type: ArtifactType,
        payload: Mapping[str, Any],
        key_id: str,
        issued_at: datetime | None = None,
    ) -> SignatureEnvelope:
        instant = (issued_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        record = self._keys.get_key_record(key_id)
        if record is None:
            raise KeyError(f"unknown signing key: {key_id}")

        required_purpose = _PURPOSE_BY_ARTIFACT[artifact_type]
        if record.purpose is not required_purpose:
            raise PermissionError(
                f"key purpose {record.purpose} cannot sign {artifact_type}"
            )
        if not record.permits_signing_at(instant):
            raise PermissionError("key is not active for the requested issue time")

        payload_hash = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        protected = {
            "alg": "EdDSA",
            "crv": "Ed25519",
            "kid": record.key_id,
            "iss": record.owner_id,
            "typ": artifact_type.value,
            "v": 1,
            "iat": int(instant.timestamp()),
            "payload_sha256": payload_hash,
        }
        signing_input = self._signing_input(protected, payload)
        signature = self._keys.sign(key_id, signing_input)

        return SignatureEnvelope(
            protected=protected,
            payload=dict(payload),
            signature=_b64url_encode(signature),
        )

    def verify_artifact(
        self,
        envelope: SignatureEnvelope,
        *,
        expected_artifact_type: ArtifactType | None = None,
        accept_revoked_for_historical_audit: bool = False,
    ) -> VerificationResult:
        try:
            protected = envelope.protected
            if protected.get("alg") != "EdDSA" or protected.get("crv") != "Ed25519":
                return VerificationResult(False, "UNSUPPORTED_ALGORITHM")
            if protected.get("v") != 1:
                return VerificationResult(False, "UNSUPPORTED_SIGNATURE_VERSION")

            key_id = protected.get("kid")
            if not isinstance(key_id, str) or not key_id:
                return VerificationResult(False, "KEY_ID_MISSING")

            try:
                artifact_type = ArtifactType(protected.get("typ"))
            except (TypeError, ValueError):
                return VerificationResult(False, "ARTIFACT_TYPE_INVALID", key_id=key_id)

            if expected_artifact_type is not None and artifact_type is not expected_artifact_type:
                return VerificationResult(
                    False,
                    "ARTIFACT_TYPE_MISMATCH",
                    key_id=key_id,
                    artifact_type=artifact_type,
                )

            record = self._keys.get_key_record(key_id)
            if record is None:
                return VerificationResult(
                    False, "KEY_NOT_FOUND", key_id=key_id, artifact_type=artifact_type
                )
            if record.owner_id != protected.get("iss"):
                return VerificationResult(
                    False, "ISSUER_MISMATCH", key_id=key_id, artifact_type=artifact_type
                )

            required_purpose = _PURPOSE_BY_ARTIFACT[artifact_type]
            if record.purpose is not required_purpose:
                return VerificationResult(
                    False,
                    "KEY_PURPOSE_MISMATCH",
                    key_id=key_id,
                    artifact_type=artifact_type,
                )
            if record.status is KeyStatus.REVOKED and not accept_revoked_for_historical_audit:
                return VerificationResult(
                    False, "KEY_REVOKED", key_id=key_id, artifact_type=artifact_type
                )

            issued_at_raw = protected.get("iat")
            if not isinstance(issued_at_raw, int):
                return VerificationResult(
                    False, "ISSUED_AT_INVALID", key_id=key_id, artifact_type=artifact_type
                )
            issued_at = datetime.fromtimestamp(issued_at_raw, tz=timezone.utc)
            if not record.not_before <= issued_at < record.not_after:
                return VerificationResult(
                    False,
                    "KEY_NOT_VALID_AT_ISSUANCE",
                    key_id=key_id,
                    artifact_type=artifact_type,
                )

            actual_hash = hashlib.sha256(
                canonical_json_bytes(envelope.payload)
            ).hexdigest()
            expected_hash = protected.get("payload_sha256")
            if not isinstance(expected_hash, str) or not hmac.compare_digest(
                actual_hash, expected_hash
            ):
                return VerificationResult(
                    False,
                    "PAYLOAD_HASH_MISMATCH",
                    key_id=key_id,
                    artifact_type=artifact_type,
                )

            public_key = Ed25519PublicKey.from_public_bytes(record.public_key)
            public_key.verify(
                _b64url_decode(envelope.signature),
                self._signing_input(protected, envelope.payload),
            )
            return VerificationResult(
                True, "VALID", key_id=key_id, artifact_type=artifact_type
            )
        except (InvalidSignature, ValueError, TypeError):
            return VerificationResult(False, "SIGNATURE_INVALID")

    @staticmethod
    def _signing_input(
        protected: Mapping[str, Any], payload: Mapping[str, Any]
    ) -> bytes:
        return _DOMAIN_PREFIX + canonical_json_bytes(
            {"protected": protected, "payload": payload}
        )
