"""Transaction-history projection persistence contracts."""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from .models import (
    SubjectKind,
    TransactionAccessAudit,
    TransactionSubjectLink,
    UttTransactionProjection,
)


class TransactionProjectionNotFoundError(LookupError):
    pass


class TransactionHistoryStore(Protocol):
    def commit(
        self,
        projection: UttTransactionProjection,
        links: tuple[TransactionSubjectLink, ...],
    ) -> UttTransactionProjection: ...
    def require_projection(self, utt_id: str) -> UttTransactionProjection: ...
    def links_for_utt(self, utt_id: str) -> tuple[TransactionSubjectLink, ...]: ...
    def list_for_subject(
        self, subject_kind: SubjectKind, subject_id: str
    ) -> tuple[tuple[UttTransactionProjection, TransactionSubjectLink], ...]: ...
    def append_audit(self, audit: TransactionAccessAudit) -> None: ...


class InMemoryTransactionHistoryStore:
    """Test adapter modelling immutable projections, links, and access audit."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._projections: dict[str, UttTransactionProjection] = {}
        self._links_by_utt: dict[str, tuple[TransactionSubjectLink, ...]] = {}
        self._utts_by_subject: dict[tuple[SubjectKind, str], set[str]] = {}
        self._audits: list[TransactionAccessAudit] = []

    def commit(
        self,
        projection: UttTransactionProjection,
        links: tuple[TransactionSubjectLink, ...],
    ) -> UttTransactionProjection:
        with self._lock:
            existing = self._projections.get(projection.utt_id)
            if existing is not None:
                if existing.utt_payload_sha256 != projection.utt_payload_sha256:
                    raise RuntimeError("UTT transaction projection conflict")
                return existing
            if not links:
                raise ValueError("UTT transaction projection requires at least one subject")
            if any(link.utt_id != projection.utt_id for link in links):
                raise ValueError("transaction link UTT does not match projection")
            unique = {(link.subject_kind, link.subject_id) for link in links}
            if len(unique) != len(links):
                raise ValueError("transaction subject links must be aggregated")
            self._projections[projection.utt_id] = projection
            self._links_by_utt[projection.utt_id] = links
            for link in links:
                key = (link.subject_kind, link.subject_id)
                self._utts_by_subject.setdefault(key, set()).add(projection.utt_id)
            return projection

    def require_projection(self, utt_id: str) -> UttTransactionProjection:
        with self._lock:
            projection = self._projections.get(utt_id)
            if projection is None:
                raise TransactionProjectionNotFoundError(
                    f"transaction projection not found: {utt_id}"
                )
            return projection

    def links_for_utt(self, utt_id: str) -> tuple[TransactionSubjectLink, ...]:
        with self._lock:
            self.require_projection(utt_id)
            return self._links_by_utt[utt_id]

    def list_for_subject(
        self, subject_kind: SubjectKind, subject_id: str
    ) -> tuple[tuple[UttTransactionProjection, TransactionSubjectLink], ...]:
        with self._lock:
            utt_ids = self._utts_by_subject.get((subject_kind, subject_id), set())
            rows = [
                (
                    self._projections[utt_id],
                    next(
                        link
                        for link in self._links_by_utt[utt_id]
                        if link.subject_kind is subject_kind and link.subject_id == subject_id
                    ),
                )
                for utt_id in utt_ids
            ]
            rows.sort(
                key=lambda row: (row[0].accepted_at, row[0].utt_id), reverse=True
            )
            return tuple(rows)

    def append_audit(self, audit: TransactionAccessAudit) -> None:
        with self._lock:
            if any(existing.audit_id == audit.audit_id for existing in self._audits):
                raise RuntimeError("transaction access audit identifier collision")
            self._audits.append(audit)

    def audits(self) -> tuple[TransactionAccessAudit, ...]:
        with self._lock:
            return tuple(self._audits)
