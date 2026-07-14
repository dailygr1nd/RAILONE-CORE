"""Atomic provider-submission and signed-outbox persistence boundary."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from threading import RLock
from typing import Protocol

from .models import OutboxRecord, ProviderSubmissionRecord


class SubmissionNotFoundError(LookupError):
    pass


class ConcurrentSubmissionUpdateError(RuntimeError):
    pass


class OperationsStore(Protocol):
    def prepare(
        self, submission: ProviderSubmissionRecord, outbox: OutboxRecord
    ) -> ProviderSubmissionRecord: ...
    def require_submission(self, rtt_id: str) -> ProviderSubmissionRecord: ...
    def transition(
        self,
        *,
        previous_version: int,
        submission: ProviderSubmissionRecord,
        outbox: OutboxRecord,
    ) -> None: ...
    def pending_outbox(self, *, limit: int = 100) -> tuple[OutboxRecord, ...]: ...
    def claim_outbox(
        self,
        *,
        worker_id: str,
        at: datetime,
        lease_seconds: int,
        limit: int,
    ) -> tuple[OutboxRecord, ...]: ...
    def mark_published(
        self, *, event_id: str, worker_id: str, at: datetime
    ) -> OutboxRecord: ...
    def reschedule(
        self,
        *,
        event_id: str,
        worker_id: str,
        at: datetime,
        available_at: datetime,
        error: str,
        max_attempts: int,
    ) -> OutboxRecord: ...


class InMemoryOperationsStore:
    """Test adapter mirroring transactional unique and CAS constraints."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._submissions_by_rtt: dict[str, ProviderSubmissionRecord] = {}
        self._rtt_by_idempotency: dict[str, str] = {}
        self._outbox: dict[str, OutboxRecord] = {}

    def prepare(
        self, submission: ProviderSubmissionRecord, outbox: OutboxRecord
    ) -> ProviderSubmissionRecord:
        with self._lock:
            existing = self._submissions_by_rtt.get(submission.rtt_id)
            if existing is not None:
                if (
                    existing.request_sha256 != submission.request_sha256
                    or existing.idempotency_key != submission.idempotency_key
                ):
                    raise RuntimeError("provider submission preparation conflict")
                return existing
            prior_rtt = self._rtt_by_idempotency.get(submission.idempotency_key)
            if prior_rtt is not None:
                raise RuntimeError(
                    f"provider idempotency key already belongs to {prior_rtt}"
                )
            if outbox.event_id in self._outbox:
                raise RuntimeError("outbox event identifier collision")
            self._submissions_by_rtt[submission.rtt_id] = submission
            self._rtt_by_idempotency[submission.idempotency_key] = submission.rtt_id
            self._outbox[outbox.event_id] = outbox
            return submission

    def require_submission(self, rtt_id: str) -> ProviderSubmissionRecord:
        with self._lock:
            submission = self._submissions_by_rtt.get(rtt_id)
            if submission is None:
                raise SubmissionNotFoundError(f"provider submission not found: {rtt_id}")
            return submission

    def transition(
        self,
        *,
        previous_version: int,
        submission: ProviderSubmissionRecord,
        outbox: OutboxRecord,
    ) -> None:
        with self._lock:
            current = self._submissions_by_rtt.get(submission.rtt_id)
            if current is None:
                raise SubmissionNotFoundError(
                    f"provider submission not found: {submission.rtt_id}"
                )
            if current.version != previous_version:
                raise ConcurrentSubmissionUpdateError(
                    "provider submission changed concurrently"
                )
            if submission.version != previous_version + 1:
                raise ValueError("submission version must advance exactly once")
            if outbox.event_id in self._outbox:
                raise RuntimeError("outbox event identifier collision")
            self._submissions_by_rtt[submission.rtt_id] = submission
            self._outbox[outbox.event_id] = outbox

    def pending_outbox(self, *, limit: int = 100) -> tuple[OutboxRecord, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("outbox limit must be between 1 and 1000")
        with self._lock:
            rows = [
                row
                for row in self._outbox.values()
                if row.delivery_state.value == "PENDING"
            ]
            rows.sort(key=lambda row: (row.available_at, row.event_id))
            return tuple(rows[:limit])

    def claim_outbox(
        self,
        *,
        worker_id: str,
        at: datetime,
        lease_seconds: int,
        limit: int,
    ) -> tuple[OutboxRecord, ...]:
        if not worker_id.strip():
            raise ValueError("outbox worker_id is required")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or not 1 <= lease_seconds <= 300:
            raise ValueError("outbox lease_seconds must be between 1 and 300")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("outbox claim limit must be between 1 and 1000")
        with self._lock:
            eligible = [
                row
                for row in self._outbox.values()
                if (
                    row.delivery_state.value == "PENDING"
                    and row.available_at <= at
                )
                or (
                    row.delivery_state.value == "IN_FLIGHT"
                    and row.lease_until is not None
                    and row.lease_until <= at
                )
            ]
            eligible.sort(key=lambda row: (row.available_at, row.event_id))
            claimed = []
            for row in eligible[:limit]:
                updated = replace(
                    row,
                    delivery_state=type(row.delivery_state).IN_FLIGHT,
                    delivery_attempts=row.delivery_attempts + 1,
                    lease_owner=worker_id,
                    lease_until=at + timedelta(seconds=lease_seconds),
                    version=row.version + 1,
                    updated_at=at,
                )
                self._outbox[row.event_id] = updated
                claimed.append(updated)
            return tuple(claimed)

    def mark_published(
        self, *, event_id: str, worker_id: str, at: datetime
    ) -> OutboxRecord:
        with self._lock:
            row = self._require_owned_event(event_id, worker_id)
            updated = replace(
                row,
                delivery_state=type(row.delivery_state).PUBLISHED,
                lease_owner=None,
                lease_until=None,
                last_error=None,
                published_at=at,
                version=row.version + 1,
                updated_at=at,
            )
            self._outbox[event_id] = updated
            return updated

    def reschedule(
        self,
        *,
        event_id: str,
        worker_id: str,
        at: datetime,
        available_at: datetime,
        error: str,
        max_attempts: int,
    ) -> OutboxRecord:
        if not error.strip():
            raise ValueError("outbox failure error is required")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 100:
            raise ValueError("outbox max_attempts must be between 1 and 100")
        with self._lock:
            row = self._require_owned_event(event_id, worker_id)
            terminal = row.delivery_attempts >= max_attempts
            updated = replace(
                row,
                delivery_state=(
                    type(row.delivery_state).DEAD_LETTER
                    if terminal
                    else type(row.delivery_state).PENDING
                ),
                available_at=available_at,
                lease_owner=None,
                lease_until=None,
                last_error=error[:1000],
                version=row.version + 1,
                updated_at=at,
            )
            self._outbox[event_id] = updated
            return updated

    def _require_owned_event(self, event_id: str, worker_id: str) -> OutboxRecord:
        row = self._outbox.get(event_id)
        if row is None:
            raise LookupError(f"outbox event not found: {event_id}")
        if row.delivery_state.value != "IN_FLIGHT" or row.lease_owner != worker_id:
            raise PermissionError("worker does not own the outbox lease")
        return row
