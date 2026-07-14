from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Protocol

from .models import SettlementEvidenceRecord, SmsDeliveryState, SmsNotificationRecord


class SettlementConflictError(RuntimeError):
    pass


class SettlementNotificationStore(Protocol):
    def commit_settlement(
        self,
        evidence: SettlementEvidenceRecord,
        notifications: tuple[SmsNotificationRecord, SmsNotificationRecord],
    ) -> tuple[SettlementEvidenceRecord, tuple[SmsNotificationRecord, SmsNotificationRecord], bool]: ...
    def require_notification(self, notification_id: str) -> SmsNotificationRecord: ...
    def transition_notification(
        self, *, previous_version: int, notification: SmsNotificationRecord
    ) -> None: ...
    def pending_notifications(self, *, limit: int = 100) -> tuple[SmsNotificationRecord, ...]: ...


class InMemorySettlementNotificationStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._evidence_by_utt: dict[str, SettlementEvidenceRecord] = {}
        self._notifications: dict[str, SmsNotificationRecord] = {}

    def commit_settlement(self, evidence, notifications):
        with self._lock:
            existing = self._evidence_by_utt.get(evidence.utt_id)
            if existing is not None:
                if existing.evidence_id != evidence.evidence_id:
                    raise SettlementConflictError(
                        "UTT received conflicting settlement evidence"
                    )
                rows = tuple(
                    self._notifications[item.notification_id] for item in notifications
                )
                return existing, rows, True
            if len({item.recipient_role for item in notifications}) != 2:
                raise ValueError("settlement requires sender and receiver notifications")
            for item in notifications:
                if item.notification_id in self._notifications:
                    raise SettlementConflictError("notification identifier collision")
            self._evidence_by_utt[evidence.utt_id] = evidence
            for item in notifications:
                self._notifications[item.notification_id] = item
            return evidence, notifications, False

    def require_notification(self, notification_id):
        with self._lock:
            row = self._notifications.get(notification_id)
            if row is None:
                raise LookupError("SMS notification not found")
            return row

    def transition_notification(self, *, previous_version, notification):
        with self._lock:
            current = self._notifications.get(notification.notification_id)
            if current is None:
                raise LookupError("SMS notification not found")
            if current.version != previous_version:
                raise RuntimeError("SMS notification changed concurrently")
            if notification.version != previous_version + 1:
                raise ValueError("SMS notification version must advance exactly once")
            self._notifications[notification.notification_id] = notification

    def pending_notifications(self, *, limit=100):
        if isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("notification limit is outside policy")
        with self._lock:
            rows = [
                item for item in self._notifications.values()
                if item.state in {SmsDeliveryState.PREPARED, SmsDeliveryState.DISPATCHING}
            ]
        rows.sort(key=lambda item: (item.created_at, item.notification_id))
        return tuple(rows[:limit])
