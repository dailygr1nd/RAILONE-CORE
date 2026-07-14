"""Exactly-once provider outcome projection persistence contract."""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from .models import ProviderOutcomeProjection


class ProjectionEventConflictError(RuntimeError):
    pass


class ProviderOutcomeProjectionStore(Protocol):
    def apply(
        self,
        *,
        event_id: str,
        event_payload_sha256: str,
        projection: ProviderOutcomeProjection,
    ) -> bool:
        """Apply once; return false for an identical already-consumed event."""
        ...

    def get(self, submission_id: str) -> ProviderOutcomeProjection | None: ...


class InMemoryProviderOutcomeProjectionStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._event_hashes: dict[str, str] = {}
        self._projections: dict[str, ProviderOutcomeProjection] = {}

    def apply(
        self,
        *,
        event_id: str,
        event_payload_sha256: str,
        projection: ProviderOutcomeProjection,
    ) -> bool:
        with self._lock:
            prior_hash = self._event_hashes.get(event_id)
            if prior_hash is not None:
                if prior_hash != event_payload_sha256:
                    raise ProjectionEventConflictError(
                        "event identifier was reused with different signed material"
                    )
                return False
            self._event_hashes[event_id] = event_payload_sha256
            current = self._projections.get(projection.submission_id)
            if current is None or projection.submission_version > current.submission_version:
                self._projections[projection.submission_id] = projection
            return True

    def get(self, submission_id: str) -> ProviderOutcomeProjection | None:
        with self._lock:
            return self._projections.get(submission_id)
