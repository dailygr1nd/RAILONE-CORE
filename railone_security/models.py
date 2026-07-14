"""Versioned encrypted-envelope contracts."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class EncryptionPurpose(StrEnum):
    ACCOUNT_ENDPOINT = "ACCOUNT_ENDPOINT"
    CONTACT_DESTINATION = "CONTACT_DESTINATION"
    PROVIDER_CREDENTIAL = "PROVIDER_CREDENTIAL"
    NOTIFICATION_BODY = "NOTIFICATION_BODY"


def decode_base64url(name: str, value: str, *, minimum: int, maximum: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty base64url text")
    if len(value) > (maximum * 4 // 3) + 8:
        raise ValueError(f"{name} exceeds the encoded size policy")
    padded = value + "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"{name} is not valid base64url") from exc
    if not minimum <= len(decoded) <= maximum:
        raise ValueError(f"{name} is outside the byte-length policy")
    return decoded


@dataclass(frozen=True, slots=True)
class EncryptedEnvelope:
    """Portable envelope; ciphertext never contains key-encryption material."""

    version: int
    algorithm: str
    key_id: str
    purpose: EncryptionPurpose
    wrapped_data_key: str
    nonce: str
    ciphertext: str
    aad_sha256: str

    def validate(self) -> None:
        if self.version != 1 or self.algorithm != "A256GCM":
            raise ValueError("unsupported encrypted-envelope profile")
        if not isinstance(self.key_id, str) or not 1 <= len(self.key_id) <= 128:
            raise ValueError("encryption key_id is invalid")
        decode_base64url("wrapped_data_key", self.wrapped_data_key, minimum=29, maximum=512)
        decode_base64url("nonce", self.nonce, minimum=12, maximum=12)
        decode_base64url("ciphertext", self.ciphertext, minimum=16, maximum=1_048_592)
        if len(self.aad_sha256) != 64:
            raise ValueError("aad_sha256 must be a SHA-256 hex digest")
        try:
            bytes.fromhex(self.aad_sha256)
        except ValueError as exc:
            raise ValueError("aad_sha256 must be hexadecimal") from exc

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "version": self.version,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "purpose": self.purpose.value,
            "wrapped_data_key": self.wrapped_data_key,
            "nonce": self.nonce,
            "ciphertext": self.ciphertext,
            "aad_sha256": self.aad_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "EncryptedEnvelope":
        required = {
            "version", "algorithm", "key_id", "purpose", "wrapped_data_key",
            "nonce", "ciphertext", "aad_sha256",
        }
        if set(value) != required:
            raise ValueError("encrypted envelope has an unexpected shape")
        try:
            envelope = cls(
                version=int(value["version"]),
                algorithm=str(value["algorithm"]),
                key_id=str(value["key_id"]),
                purpose=EncryptionPurpose(str(value["purpose"])),
                wrapped_data_key=str(value["wrapped_data_key"]),
                nonce=str(value["nonce"]),
                ciphertext=str(value["ciphertext"]),
                aad_sha256=str(value["aad_sha256"]),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("encrypted envelope fields are invalid") from exc
        envelope.validate()
        return envelope
