"""AES-256-GCM envelope encryption with canonical associated data."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from railone_crypto.canonical_json import canonical_json_bytes

from .key_provider import KeyEncryptionProvider
from .models import EncryptedEnvelope, EncryptionPurpose, decode_base64url


class EnvelopeIntegrityError(PermissionError):
    pass


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class EnvelopeEncryptionService:
    MAX_PLAINTEXT_BYTES = 1_048_576

    def __init__(self, *, keys: KeyEncryptionProvider, active_key_ids: dict[EncryptionPurpose, str]) -> None:
        missing = set(EncryptionPurpose) - set(active_key_ids)
        if missing:
            raise ValueError("active encryption key mapping is incomplete")
        self._keys = keys
        self._active_key_ids = dict(active_key_ids)

    def encrypt_text(
        self, *, purpose: EncryptionPurpose, record_id: str, owner_id: str,
        field_name: str, plaintext: str,
    ) -> EncryptedEnvelope:
        if not isinstance(plaintext, str) or not plaintext:
            raise ValueError("sensitive plaintext must be non-empty text")
        return self.encrypt(
            purpose=purpose, record_id=record_id, owner_id=owner_id,
            field_name=field_name, plaintext=plaintext.encode("utf-8"),
        )

    def encrypt(
        self, *, purpose: EncryptionPurpose, record_id: str, owner_id: str,
        field_name: str, plaintext: bytes,
    ) -> EncryptedEnvelope:
        if not isinstance(plaintext, bytes) or not 1 <= len(plaintext) <= self.MAX_PLAINTEXT_BYTES:
            raise ValueError("sensitive plaintext is outside the size policy")
        context = self._context(
            purpose=purpose, record_id=record_id, owner_id=owner_id,
            field_name=field_name,
        )
        key_id = self._active_key_ids[purpose]
        data_key = secrets.token_bytes(32)
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(data_key).encrypt(nonce, plaintext, context)
        wrapped = self._keys.wrap_key(
            key_id=key_id, data_key=data_key, context=hashlib.sha256(context).digest()
        )
        result = EncryptedEnvelope(
            version=1, algorithm="A256GCM", key_id=key_id, purpose=purpose,
            wrapped_data_key=_encode(wrapped), nonce=_encode(nonce),
            ciphertext=_encode(ciphertext),
            aad_sha256=hashlib.sha256(context).hexdigest(),
        )
        result.validate()
        return result

    def decrypt_text(
        self, *, envelope: EncryptedEnvelope, purpose: EncryptionPurpose,
        record_id: str, owner_id: str, field_name: str,
    ) -> str:
        try:
            return self.decrypt(
                envelope=envelope, purpose=purpose, record_id=record_id,
                owner_id=owner_id, field_name=field_name,
            ).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EnvelopeIntegrityError("decrypted value is not UTF-8") from exc

    def decrypt(
        self, *, envelope: EncryptedEnvelope, purpose: EncryptionPurpose,
        record_id: str, owner_id: str, field_name: str,
    ) -> bytes:
        envelope.validate()
        if envelope.purpose is not purpose:
            raise EnvelopeIntegrityError("encrypted value purpose mismatch")
        context = self._context(
            purpose=purpose, record_id=record_id, owner_id=owner_id,
            field_name=field_name,
        )
        digest = hashlib.sha256(context).hexdigest()
        if not hmac.compare_digest(digest, envelope.aad_sha256):
            raise EnvelopeIntegrityError("encrypted value context mismatch")
        try:
            wrapped = decode_base64url(
                "wrapped_data_key", envelope.wrapped_data_key, minimum=29, maximum=512
            )
            nonce = decode_base64url("nonce", envelope.nonce, minimum=12, maximum=12)
            ciphertext = decode_base64url(
                "ciphertext", envelope.ciphertext, minimum=16, maximum=1_048_592
            )
            data_key = self._keys.unwrap_key(
                key_id=envelope.key_id, wrapped_key=wrapped,
                context=hashlib.sha256(context).digest(),
            )
            return AESGCM(data_key).decrypt(nonce, ciphertext, context)
        except (InvalidTag, ValueError, LookupError) as exc:
            raise EnvelopeIntegrityError("encrypted value failed authentication") from exc

    @staticmethod
    def _context(
        *, purpose: EncryptionPurpose, record_id: str, owner_id: str,
        field_name: str,
    ) -> bytes:
        values = {
            "domain": "RAILONE-ENVELOPE-AAD-V1", "purpose": purpose.value,
            "record_id": record_id, "owner_id": owner_id, "field_name": field_name,
        }
        for name in ("record_id", "owner_id", "field_name"):
            value = values[name]
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{name} is invalid")
        return canonical_json_bytes(values)
