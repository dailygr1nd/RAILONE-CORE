"""Persistence contract for encrypted values only."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from .models import EncryptedEnvelope


@dataclass(frozen=True, slots=True)
class EncryptedSecretRecord:
    vault_name: str
    record_id: str
    owner_id: str
    envelope: EncryptedEnvelope
    plaintext_sha256: str


class EncryptedSecretStore(Protocol):
    def put(self, record: EncryptedSecretRecord) -> EncryptedSecretRecord: ...
    def require(self, *, vault_name: str, record_id: str) -> EncryptedSecretRecord: ...


class InMemoryEncryptedSecretStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[tuple[str, str], EncryptedSecretRecord] = {}

    def put(self, record: EncryptedSecretRecord) -> EncryptedSecretRecord:
        key = (record.vault_name, record.record_id)
        with self._lock:
            existing = self._records.get(key)
            if existing is not None:
                if existing != record:
                    raise RuntimeError("encrypted secret immutability conflict")
                return existing
            self._records[key] = record
            return record

    def require(self, *, vault_name: str, record_id: str) -> EncryptedSecretRecord:
        with self._lock:
            try:
                return self._records[(vault_name, record_id)]
            except KeyError as exc:
                raise LookupError("encrypted secret was not found") from exc
