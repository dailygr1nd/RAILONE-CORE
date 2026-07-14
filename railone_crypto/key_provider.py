"""Key lifecycle metadata and Ed25519 signing-provider contracts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class KeyPurpose(StrEnum):
    QUOTE_SIGNING = "QUOTE_SIGNING"
    EXECUTION_SIGNING = "EXECUTION_SIGNING"
    IDENTITY_SIGNING = "IDENTITY_SIGNING"
    SETTLEMENT_SIGNING = "SETTLEMENT_SIGNING"
    REPLAY_SIGNING = "REPLAY_SIGNING"
    ACCESS_TOKEN_SIGNING = "ACCESS_TOKEN_SIGNING"
    API_AUDIT_SIGNING = "API_AUDIT_SIGNING"


class KeyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class KeyRecord:
    key_id: str
    owner_id: str
    purpose: KeyPurpose
    public_key: bytes
    status: KeyStatus
    not_before: datetime
    not_after: datetime
    created_at: datetime
    rotation_parent_id: str | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    algorithm: str = "EdDSA"
    curve: str = "Ed25519"

    def __post_init__(self) -> None:
        for field_name in ("not_before", "not_after", "created_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")

        if self.not_after <= self.not_before:
            raise ValueError("not_after must be later than not_before")

        if len(self.public_key) != 32:
            raise ValueError("Ed25519 public key must contain 32 raw bytes")

        if self.status is KeyStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked keys require revoked_at")

    def permits_signing_at(self, instant: datetime) -> bool:
        return (
            self.status is KeyStatus.ACTIVE
            and self.not_before <= instant < self.not_after
        )


class SigningKeyProvider(Protocol):
    """Boundary implemented by an isolated signer, HSM, or KMS adapter."""

    def get_key_record(self, key_id: str) -> KeyRecord | None:
        ...

    def sign(self, key_id: str, message: bytes) -> bytes:
        ...


class InMemoryEd25519KeyProvider:
    """Test-only Ed25519 key provider.

    This class intentionally performs no persistence and must not be used as a
    production keystore.
    """

    def __init__(self) -> None:
        self._records: dict[str, KeyRecord] = {}
        self._private_keys: dict[str, Ed25519PrivateKey] = {}

    def generate(
        self,
        *,
        key_id: str,
        owner_id: str,
        purpose: KeyPurpose,
        not_before: datetime,
        not_after: datetime,
        rotation_parent_id: str | None = None,
    ) -> KeyRecord:
        if key_id in self._records:
            raise ValueError(f"duplicate key_id: {key_id}")

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        record = KeyRecord(
            key_id=key_id,
            owner_id=owner_id,
            purpose=purpose,
            public_key=public_key,
            status=KeyStatus.ACTIVE,
            not_before=not_before.astimezone(timezone.utc),
            not_after=not_after.astimezone(timezone.utc),
            created_at=datetime.now(timezone.utc),
            rotation_parent_id=rotation_parent_id,
        )
        self._records[key_id] = record
        self._private_keys[key_id] = private_key
        return record

    def get_key_record(self, key_id: str) -> KeyRecord | None:
        return self._records.get(key_id)

    def sign(self, key_id: str, message: bytes) -> bytes:
        private_key = self._private_keys.get(key_id)
        if private_key is None:
            raise KeyError(f"signing key not found: {key_id}")
        return private_key.sign(message)

    def retire(self, key_id: str) -> KeyRecord:
        record = self._require_record(key_id)
        updated = replace(record, status=KeyStatus.RETIRED)
        self._records[key_id] = updated
        self._private_keys.pop(key_id, None)
        return updated

    def revoke(
        self,
        key_id: str,
        *,
        reason: str,
        revoked_at: datetime | None = None,
    ) -> KeyRecord:
        if not reason.strip():
            raise ValueError("revocation reason is required")

        record = self._require_record(key_id)
        updated = replace(
            record,
            status=KeyStatus.REVOKED,
            revoked_at=(revoked_at or datetime.now(timezone.utc)).astimezone(
                timezone.utc
            ),
            revocation_reason=reason,
        )
        self._records[key_id] = updated
        self._private_keys.pop(key_id, None)
        return updated

    def _require_record(self, key_id: str) -> KeyRecord:
        record = self.get_key_record(key_id)
        if record is None:
            raise KeyError(f"key record not found: {key_id}")
        return record
