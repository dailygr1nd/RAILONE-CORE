from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Mapping, Protocol

from .models import CallbackInboxRecord, CallbackState


class CallbackPayloadConflictError(RuntimeError):
    pass


class CallbackInboxStore(Protocol):
    def ingest(
        self,
        *,
        provider_id: str,
        provider_event_id: str,
        payload_sha256: str,
        normalized_payload: Mapping[str, object],
        signature_valid: bool,
        received_at: datetime,
    ) -> tuple[CallbackInboxRecord, bool]: ...
    def mark_applied(
        self, *, provider_id: str, provider_event_id: str, at: datetime
    ) -> CallbackInboxRecord: ...


class InMemoryCallbackInboxStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[tuple[str, str], CallbackInboxRecord] = {}

    def ingest(
        self,
        *,
        provider_id: str,
        provider_event_id: str,
        payload_sha256: str,
        normalized_payload: Mapping[str, object],
        signature_valid: bool,
        received_at: datetime,
    ) -> tuple[CallbackInboxRecord, bool]:
        key = (provider_id, provider_event_id)
        with self._lock:
            existing = self._records.get(key)
            if existing is not None:
                if existing.payload_sha256 != payload_sha256:
                    raise CallbackPayloadConflictError(
                        "provider callback identifier was reused with different material"
                    )
                return existing, True
            record = CallbackInboxRecord(
                provider_id=provider_id, provider_event_id=provider_event_id,
                payload_sha256=payload_sha256,
                normalized_payload=normalized_payload,
                signature_valid=signature_valid, state=CallbackState.RECEIVED,
                received_at=received_at, applied_at=None,
            )
            self._records[key] = record
            return record, False

    def mark_applied(
        self, *, provider_id: str, provider_event_id: str, at: datetime
    ) -> CallbackInboxRecord:
        key = (provider_id, provider_event_id)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                raise LookupError("provider callback not found")
            if record.state is CallbackState.APPLIED:
                return record
            updated = replace(record, state=CallbackState.APPLIED, applied_at=at)
            self._records[key] = updated
            return updated

    def get(self, provider_id: str, provider_event_id: str) -> CallbackInboxRecord | None:
        with self._lock:
            return self._records.get((provider_id, provider_event_id))
