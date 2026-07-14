"""Key-encryption boundary.

The application receives only wrapped per-record data keys. A production
implementation delegates these calls to an isolated KMS/HSM service.
"""

from __future__ import annotations

import secrets
from threading import RLock
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class KeyEncryptionProvider(Protocol):
    def wrap_key(self, *, key_id: str, data_key: bytes, context: bytes) -> bytes: ...
    def unwrap_key(self, *, key_id: str, wrapped_key: bytes, context: bytes) -> bytes: ...


class IsolatedKeyServiceClient(Protocol):
    """Transport-neutral client for a KMS/HSM-backed key service."""

    def wrap(self, *, key_id: str, plaintext: bytes, context: bytes) -> bytes: ...
    def unwrap(self, *, key_id: str, ciphertext: bytes, context: bytes) -> bytes: ...


class RemoteKeyEncryptionProvider:
    def __init__(self, client: IsolatedKeyServiceClient) -> None:
        self._client = client

    def wrap_key(self, *, key_id: str, data_key: bytes, context: bytes) -> bytes:
        if len(data_key) != 32:
            raise ValueError("AES-256 data key must contain 32 bytes")
        return self._client.wrap(key_id=key_id, plaintext=data_key, context=context)

    def unwrap_key(self, *, key_id: str, wrapped_key: bytes, context: bytes) -> bytes:
        value = self._client.unwrap(
            key_id=key_id, ciphertext=wrapped_key, context=context
        )
        if len(value) != 32:
            raise ValueError("isolated key service returned an invalid data key")
        return value


class InMemoryAesGcmKeyEncryptionProvider:
    """Test-only KEK adapter. It must never be used for deployed pilot keys."""

    simulation_only = True

    def __init__(self) -> None:
        self._lock = RLock()
        self._keys: dict[str, bytes] = {}

    def register(self, *, key_id: str, key: bytes) -> None:
        if not isinstance(key_id, str) or not key_id.strip() or len(key_id) > 128:
            raise ValueError("key_id is invalid")
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("AES-256 KEK must contain exactly 32 bytes")
        with self._lock:
            if key_id in self._keys:
                raise ValueError("key_id is already registered")
            self._keys[key_id] = key

    def wrap_key(self, *, key_id: str, data_key: bytes, context: bytes) -> bytes:
        if len(data_key) != 32:
            raise ValueError("AES-256 data key must contain exactly 32 bytes")
        nonce = secrets.token_bytes(12)
        return nonce + AESGCM(self._require(key_id)).encrypt(
            nonce, data_key, b"RAILONE-DEK-WRAP-V1\x00" + context
        )

    def unwrap_key(self, *, key_id: str, wrapped_key: bytes, context: bytes) -> bytes:
        if not 40 <= len(wrapped_key) <= 512:
            raise ValueError("wrapped data key is outside policy")
        value = AESGCM(self._require(key_id)).decrypt(
            wrapped_key[:12], wrapped_key[12:], b"RAILONE-DEK-WRAP-V1\x00" + context
        )
        if len(value) != 32:
            raise ValueError("unwrapped data key is invalid")
        return value

    def _require(self, key_id: str) -> bytes:
        with self._lock:
            try:
                return self._keys[key_id]
            except KeyError as exc:
                raise LookupError(f"encryption key is unavailable: {key_id}") from exc
