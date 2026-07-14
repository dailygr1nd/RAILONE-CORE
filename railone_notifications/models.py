"""Settlement evidence and privacy-safe SMS outbox models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from railone_crypto.signature_service import SignatureEnvelope


class NotificationRecipientRole(StrEnum):
    SENDER = "SENDER"
    RECEIVER = "RECEIVER"


class SmsDeliveryState(StrEnum):
    PREPARED = "PREPARED"
    DISPATCHING = "DISPATCHING"
    SENT = "SENT"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SettlementEvidenceRecord:
    evidence_id: str
    utt_id: str
    provider_id: str
    provider_transaction_id: str
    callback_event_id: str
    signed_evidence: SignatureEnvelope
    settled_at: datetime


@dataclass(frozen=True, slots=True)
class SmsNotificationRecord:
    notification_id: str
    evidence_id: str
    utt_id: str
    recipient_role: NotificationRecipientRole
    contact_binding_id: str = field(repr=False)
    template_version: str = "settled-sms-v1"
    rendered_body: str = field(default="", repr=False)
    body_sha256: str = ""
    state: SmsDeliveryState = SmsDeliveryState.PREPARED
    gateway_reference: str | None = None
    normalized_code: str | None = None
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SettlementNotificationResult:
    evidence: SettlementEvidenceRecord
    notifications: tuple[SmsNotificationRecord, SmsNotificationRecord]
    replayed: bool


@dataclass(frozen=True, slots=True)
class SmsGatewayResult:
    accepted: bool
    code: str
    gateway_reference: str | None = None
